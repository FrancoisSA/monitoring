#!/usr/bin/env python3
"""
build_app.py — Crée PiMonitor.app : raccourci de lancement SSH vers le Pi.
Aucune dépendance externe (pas de PIL).
"""
import shutil
import stat
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────
APP_NAME = "PiMonitor"
PI_HOST  = "FSA-PI5.local"
PI_USER  = "fsalazar"
PI_KEY   = "~/.ssh/id_ed25519"
PI_CMD   = "python3 ~/monitor/monitor.py"

APP_PATH = Path(__file__).parent / f"{APP_NAME}.app"

# ── Contenu ────────────────────────────────────────────────────────────────────

LAUNCH_SH = f"""\
#!/bin/bash
osascript <<'APPLESCRIPT'
tell application "Terminal"
    activate
    set win to do script "ssh -t -i {PI_KEY} {PI_USER}@{PI_HOST} '{PI_CMD}'"
    delay 0.4
    tell front window
        set custom title of selected tab to "Pi Monitor — {PI_HOST}"
        set zoomed to true
    end tell
end tell
APPLESCRIPT
"""

INFO_PLIST = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
    <key>CFBundleName</key>           <string>{APP_NAME}</string>
    <key>CFBundleDisplayName</key>    <string>{APP_NAME}</string>
    <key>CFBundleIdentifier</key>     <string>com.local.pimonitor</string>
    <key>CFBundleVersion</key>        <string>1.0</string>
    <key>CFBundlePackageType</key>    <string>APPL</string>
    <key>CFBundleExecutable</key>     <string>{APP_NAME}</string>
    <key>CFBundleIconFile</key>       <string>AppIcon</string>
    <key>LSMinimumSystemVersion</key> <string>12.0</string>
    <key>NSHighResolutionCapable</key> <true/>
</dict></plist>
"""

# ── Build ──────────────────────────────────────────────────────────────────────

def build() -> None:
    if APP_PATH.exists():
        shutil.rmtree(APP_PATH)

    macos = APP_PATH / "Contents" / "MacOS"
    res   = APP_PATH / "Contents" / "Resources"
    macos.mkdir(parents=True)
    res.mkdir(parents=True)

    (APP_PATH / "Contents" / "Info.plist").write_text(INFO_PLIST)
    print("  ✓ Info.plist")

    exe = macos / APP_NAME
    exe.write_text(LAUNCH_SH)
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    print(f"  ✓ Exécutable : {exe.name}")

    # Icône : emprunte celle de Terminal.app (pas de PIL nécessaire)
    for candidate in [
        Path("/System/Applications/Utilities/Terminal.app/Contents/Resources/Terminal.icns"),
        Path("/Applications/Utilities/Terminal.app/Contents/Resources/Terminal.icns"),
    ]:
        if candidate.exists():
            shutil.copy(candidate, res / "AppIcon.icns")
            print("  ✓ Icône (Terminal.app)")
            break

    print(f"\n  App créée : {APP_PATH}")
    print(f"  → Glisse PiMonitor.app dans /Applications ou sur le Dock.\n")


if __name__ == "__main__":
    print(f"\nCréation de {APP_NAME}.app…\n")
    build()
