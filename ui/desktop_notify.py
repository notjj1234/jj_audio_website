"""Best-effort OS notifications for isolate job completion.

Never raises into the UI. No extra pip dependencies: macOS uses osascript,
Windows a PowerShell balloon tip, Linux notify-send when present.
"""

from __future__ import annotations

import subprocess
import sys

NOTIFY_APP_TITLE = "Audio Isolation"


def _one_line(text: str) -> str:
    return " ".join((text or "").split())


def escape_applescript(text: str) -> str:
    """Escape a string for use inside an AppleScript double-quoted literal."""
    return _one_line(text).replace("\\", "\\\\").replace('"', '\\"')


def escape_powershell_single(text: str) -> str:
    """Escape a string for use inside a PowerShell single-quoted literal."""
    return _one_line(text).replace("'", "''")


def _notify_command(platform: str, title: str, body: str) -> list[str] | None:
    title = _one_line(title) or NOTIFY_APP_TITLE
    body = _one_line(body)
    if platform == "darwin":
        script = (
            f'display notification "{escape_applescript(body)}" '
            f'with title "{escape_applescript(title)}"'
        )
        return ["osascript", "-e", script]
    if platform == "win32":
        t = escape_powershell_single(title)
        b = escape_powershell_single(body)
        script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "Add-Type -AssemblyName System.Drawing; "
            "$n = New-Object System.Windows.Forms.NotifyIcon; "
            "$n.Icon = [System.Drawing.SystemIcons]::Information; "
            "$n.Visible = $true; "
            f"$n.ShowBalloonTip(5000, '{t}', '{b}', "
            "[System.Windows.Forms.ToolTipIcon]::Info); "
            "Start-Sleep -Seconds 5; "
            "$n.Dispose()"
        )
        return [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            script,
        ]
    return ["notify-send", title, body]


def notify(
    title: str,
    body: str,
    *,
    platform: str | None = None,
    runner=None,
) -> bool:
    """Show a non-blocking OS notification. Returns False if the attempt failed."""
    plat = platform if platform is not None else sys.platform
    cmd = _notify_command(plat, title, body)
    if not cmd:
        return False
    try:
        if runner is None and plat == "win32":
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True
        run = runner or subprocess.run
        run(cmd, check=False, capture_output=True, timeout=8)
        return True
    except Exception:
        return False
