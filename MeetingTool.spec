# -*- mode: python ; coding: utf-8 -*-
"""
MeetingTool.spec - PyInstaller build config (MeetingTool v2.5)
==============================================================
Target : Windows ARM64, Python 3.13, PyInstaller >= 6.21.0
Mode   : onedir (CustomTkinter ships data files; onedir is more reliable
         than onefile on ARM64 and starts faster).

Build  : pyinstaller MeetingTool.spec        (or run build.ps1)
Output : dist/MeetingTool/MeetingTool.exe

Notes:
  - CustomTkinter theme JSON + assets are collected as data files; without
    them CTk crashes at startup looking for blue.json.
  - scikit-image is collected wholesale (lazy submodule imports PyInstaller
    misses otherwise).
  - 'anthropic' is excluded: the automated pipeline (claude_client.py) is
    dormant and not reachable from the Cowork GUI flow (Inc 7 decision).
  - ffmpeg is a SYSTEM dependency (PATH), intentionally not bundled.
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = []
datas += collect_data_files("customtkinter")

hiddenimports = []
hiddenimports += collect_submodules("skimage")
hiddenimports += [
    "PIL._tkinter_finder",
    "tools.runner",
    "tools.extract_frames",
    "tools.exporter",
    "tools.prompt_generator",
    "tools.project",
    "tools.installer",
    "tools.api_config",
    "gui.app",
    "gui.main_window",
    "gui.settings",
    "gui.setup_window",
    "gui.project_window",
    "gui.next_steps_window",
    "gui.styles",
]

excludes = [
    "anthropic",      # dormant pipeline - keep source, drop from binary
    "matplotlib",     # pulled optionally by skimage; unused here
    "pytest",         # test-only
    "PyInstaller",    # build-time only
]

block_cipher = None

a = Analysis(
    ["MeetingTool.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MeetingTool",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,           # GUI app - no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MeetingTool",
)
