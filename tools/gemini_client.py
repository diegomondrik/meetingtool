"""
tools/gemini_client.py — MeetingTool v2.5
==========================================
Sends meeting frames to Google Gemini 1.5 Flash for visual extraction.

Uses the Gemini REST API directly (no google-genai SDK) to avoid native
binary dependencies (cryptography/grpcio) that fail on ARM64 Windows.

Pipeline:
  1. Split frames into chunks of CHUNK_SIZE (~37 frames each)
  2. POST each chunk to Gemini with the vision prompt
  3. Collect text responses and concatenate into visual_evidence string
  4. On HTTP 429: wait RETRY_DELAY seconds and retry once
  5. On persistent failure: raise GeminiUnavailableError → caller activates OCR fallback
"""

import base64
import json
import logging
import time
from pathlib import Path

import requests

log = logging.getLogger("gemini_client")

GEMINI_MODEL    = "gemini-1.5-flash"
GEMINI_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

CHUNK_SIZE   = 38    # frames per request — 4 chunks for 150 frames (38+38+38+36)
CHUNK_DELAY  = 4.0   # seconds between chunks (TPM rate limit)
RETRY_DELAY  = 15.0  # seconds to wait after HTTP 429 before single retry
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
"""


class GeminiUnavailableError(Exception):
    """Raised when Gemini is unreachable or rate-limited after retry."""
    pass


def _encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def _build_payload(frame_paths: list[Path], chunk_index: int) -> dict:
    """Build the JSON payload for one chunk of frames."""
    parts = [{"text": VISION_PROMPT}]

    for i, path in enumerate(frame_paths):
        global_n = chunk_index * CHUNK_SIZE + i + 1
        parts.append({
            "text": f"[FRAME {global_n}] — {path.name}"
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


def extract_visual_evidence(frame_paths: list[Path], api_key: str) -> str:
    """
    Send all frames to Gemini in chunks and return the combined visual_evidence string.

    Args:
        frame_paths: Ordered list of JPEG frame paths.
        api_key:     Gemini API key (from api_config.get_gemini_key()).

    Returns:
        Single string combining all chunk responses — the visual_evidence
        payload passed to the Claude stage.

    Raises:
        GeminiUnavailableError: If Gemini fails after one retry. Caller
                                should activate the OCR fallback.
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
    )

    results = []

    for idx, chunk in enumerate(chunks):
        log.info(f"  Chunk {idx + 1}/{len(chunks)}: {len(chunk)} frames...")
        payload = _build_payload(chunk, idx)

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
