"""
tools/gemini_client.py — MeetingTool v2.5
==========================================
Sends meeting frames to Google Gemini 1.5 Flash for visual extraction.

Uses the Gemini REST API directly (no google-genai SDK) to avoid native
binary dependencies (cryptography/grpcio) that fail on ARM64 Windows.

Pipeline:
  1. Split frames into chunks of CHUNK_SIZE (70 frames, ~38k tokens each)
  2. POST each chunk to Gemini with the vision prompt
  3. Wait CHUNK_DELAY (65s) between chunks to stay within free-tier 40k TPM window
  4. On HTTP 429: wait RETRY_DELAY (65s) and retry once
  5. On persistent failure: raise GeminiUnavailableError → caller activates OCR fallback
"""

import base64
import json
import logging
import time
from pathlib import Path

import requests

log = logging.getLogger("gemini_client")

GEMINI_MODEL    = "gemini-2.0-flash"
GEMINI_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

# Free-tier TPM limit: 40,000 tokens/min.
# 720p frame = 2 tiles × 258 = 516 tokens. Prompt overhead ≈ 2,000 tokens.
# Max safe frames per chunk: (40,000 - 2,000) / 516 ≈ 73. Using 70 for buffer.
# Delay between chunks must be ≥ 60s so consecutive chunks don't merge into
# the same TPM window.
CHUNK_SIZE   = 70    # frames per request — stays under 40k TPM per window
CHUNK_DELAY  = 65.0  # seconds between chunks — ensures a new 1-min TPM window
RETRY_DELAY  = 65.0  # seconds to wait after HTTP 429 before single retry
REQUEST_TIMEOUT = 120  # seconds per request

VISION_PROMPT = """You are analyzing screenshots from a business meeting recording.
For each image provided, extract all visible structured information.

Output format — one block per image, in sequence:

[FRAME {n}]
- Window/App: <active application or window title>
- Content Type: <slide | spreadsheet | ERP | email | dashboard | code | video-call | other>
- Key Data: <tables, numbers, KPIs, metrics — copy exact values if visible>
- Text: <headings, bullet points, labels, code snippets, formulas>
- Notable: <anything highlighted, flagged, referenced, or unusual>

Rules:
- Extract data precisely — do not paraphrase numbers or metrics
- Ignore empty participant video panels (plain black/grey rectangles)
- If an image is too blurry or uninformative, write: [FRAME {n}] - Content: uninformative
- Output plain text, no markdown headers
- If a value or text is partially visible or unclear, mark it explicitly as
  [ILLEGIBLE] rather than omitting it or guessing.
- Capture non-text visual signals: elements in red/green/orange (alert states),
  the largest or most visually prominent element on screen, any visual emphasis
  (bold, large font, highlighted cell).
- If this frame looks visually similar to previous frames in the session,
  state what changed vs. what remained the same.
"""


class GeminiUnavailableError(Exception):
    """Raised when Gemini is unreachable or rate-limited after retry."""
    pass


def _encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def _build_payload(frame_paths: list[Path], chunk_index: int,
                   transcript_segments: dict | None = None) -> dict:
    """Build the JSON payload for one chunk of frames.

    transcript_segments: optional dict of {frame_global_index: transcript_snippet}.
    When present, the snippet for a frame is injected as context before its image.
    """
    parts = [{"text": VISION_PROMPT}]

    for i, path in enumerate(frame_paths):
        global_n = chunk_index * CHUNK_SIZE + i + 1
        parts.append({
            "text": f"[FRAME {global_n}] — {path.name}"
        })
        if transcript_segments and global_n in transcript_segments:
            parts.append({
                "text": f"[Speaker context at this moment]: {transcript_segments[global_n]}"
            })
        parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": _encode_image(path),
            }
        })

    return {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature":    0.1,   # low variance — we want factual extraction
            "maxOutputTokens": 4096,
        },
    }


def _post_chunk(payload: dict, api_key: str) -> str:
    """POST one chunk to Gemini. Returns the response text. Raises on error."""
    response = requests.post(
        GEMINI_ENDPOINT,
        params={"key": api_key},
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code == 429:
        raise requests.HTTPError("429 rate limited", response=response)

    if response.status_code != 200:
        raise requests.HTTPError(
            f"Gemini returned HTTP {response.status_code}: {response.text[:200]}",
            response=response,
        )

    data = response.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise ValueError(f"Unexpected Gemini response shape: {data}") from exc


def extract_visual_evidence(frame_paths: list[Path], api_key: str,
                            transcript_segments: dict | None = None,
                            api_key_2: str | None = None) -> str:
    """
    Send all frames to Gemini in chunks and return the combined visual_evidence string.

    Args:
        frame_paths:          Ordered list of JPEG frame paths.
        api_key:              Primary Gemini API key.
        transcript_segments:  Optional dict of {frame_global_index: transcript_snippet}.
        api_key_2:            Optional backup Gemini key. When key 1 is exhausted on a
                              429 after retry, key 2 is tried before raising
                              GeminiUnavailableError.

    Returns:
        Single string combining all chunk responses — the visual_evidence
        payload passed to the Claude stage.

    Raises:
        GeminiUnavailableError: If Gemini fails after all retry/fallback attempts.
                                Caller should activate the OCR fallback.
    """
    if not frame_paths:
        log.warning("No frames provided to Gemini — returning empty visual_evidence")
        return ""

    chunks = [
        frame_paths[i : i + CHUNK_SIZE]
        for i in range(0, len(frame_paths), CHUNK_SIZE)
    ]

    log.info(
        f"Sending {len(frame_paths)} frames to Gemini in {len(chunks)} chunk(s) "
        f"({CHUNK_SIZE} frames each, {CHUNK_DELAY}s delay)"
        + (" [with transcript context]" if transcript_segments else "")
    )

    results = []

    for idx, chunk in enumerate(chunks):
        log.info(f"  Chunk {idx + 1}/{len(chunks)}: {len(chunk)} frames...")
        payload = _build_payload(chunk, idx, transcript_segments)

        try:
            text = _post_chunk(payload, api_key)
            results.append(text)
            log.info(f"  Chunk {idx + 1} OK ({len(text)} chars)")

        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                log.warning(
                    f"  Chunk {idx + 1}: HTTP 429 — waiting {RETRY_DELAY}s then retrying..."
                )
                time.sleep(RETRY_DELAY)
                try:
                    text = _post_chunk(payload, api_key)
                    results.append(text)
                    log.info(f"  Chunk {idx + 1} retry OK")
                except Exception as retry_exc:
                    if api_key_2:
                        log.warning(
                            f"  Chunk {idx + 1}: key 1 exhausted — switching to backup key..."
                        )
                        try:
                            text = _post_chunk(payload, api_key_2)
                            results.append(text)
                            log.info(f"  Chunk {idx + 1} OK via backup key")
                        except Exception as key2_exc:
                            raise GeminiUnavailableError(
                                f"Gemini rate-limited on chunk {idx + 1}, both keys failed: {key2_exc}"
                            ) from key2_exc
                    else:
                        raise GeminiUnavailableError(
                            f"Gemini rate-limited on chunk {idx + 1} after retry: {retry_exc}"
                        ) from retry_exc
            else:
                raise GeminiUnavailableError(
                    f"Gemini error on chunk {idx + 1}: {exc}"
                ) from exc

        except Exception as exc:
            raise GeminiUnavailableError(
                f"Gemini unreachable on chunk {idx + 1}: {exc}"
            ) from exc

        if idx < len(chunks) - 1:
            log.info(f"  Waiting {CHUNK_DELAY}s before next chunk...")
            time.sleep(CHUNK_DELAY)

    visual_evidence = "\n\n".join(results)
    log.info(
        f"Gemini extraction complete: {len(results)} chunk(s), "
        f"{len(visual_evidence)} total chars"
    )
    return visual_evidence
