#!/usr/bin/env python3
"""Sign and notarize AudioTools.app / .pkg so Gatekeeper accepts downloads.

Apple only accepts Developer ID Application + Developer ID Installer for
distribution outside the App Store. An Apple Development certificate is not
enough — notarization rejects it, and macOS Sequoia blocks the .pkg.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

ENTITLEMENTS = Path(__file__).resolve().parent / "entitlements.plist"

MACH_O_MAGICS = {
    b"\xcf\xfa\xed\xfe",
    b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf",
    b"\xfe\xed\xfa\xce",
    b"\xca\xfe\xba\xbe",
    b"\xbe\xba\xfe\xca",
    b"\xca\xfe\xba\xbf",
    b"\xbf\xba\xfe\xca",
}

IDENTITY_RE = re.compile(r'^\s*\d+\)\s+[A-F0-9]+\s+"([^"]+)"\s*$', re.MULTILINE)

_MISSING_DEVELOPER_ID = """\
macOS Gatekeeper will block this .pkg for other users until it is signed with
Developer ID Application + Developer ID Installer and notarized by Apple.

This machine has no Developer ID certificates. An Apple Development certificate
cannot be notarized and does not silence the malware dialog.

1. Enroll in the Apple Developer Program ($99/year):
   https://developer.apple.com/programs/
2. In Xcode → Settings → Accounts → Manage Certificates, create
   Developer ID Application and Developer ID Installer.
3. Store notary credentials once:
   xcrun notarytool store-credentials audio-tools-notary
4. Re-run: AUDIO_TOOLS_VERSION=0.1.0 ./packaging/make_pkg.sh

Optional env: AUDIO_TOOLS_SIGN_APPLICATION, AUDIO_TOOLS_SIGN_INSTALLER,
AUDIO_TOOLS_NOTARY_PROFILE, AUDIO_TOOLS_REQUIRE_NOTARIZE=1
"""


@dataclass(frozen=True)
class SigningIdentities:
    application: Optional[str]
    installer: Optional[str]

    def can_distribute(self) -> bool:
        return bool(self.application and self.installer)


def parse_identities(output: str) -> SigningIdentities:
    """Keep only Developer ID certs — Apple Development is development-only."""
    application = None
    installer = None
    for name in IDENTITY_RE.findall(output):
        if name.startswith("Developer ID Application:"):
            application = name
        elif name.startswith("Developer ID Installer:"):
            installer = name
    return SigningIdentities(application=application, installer=installer)


def codesign_app_commands(
    app: Path,
    identity: str,
    entitlements: Path,
    macho_files: List[Path],
) -> List[List[str]]:
    common = [
        "codesign",
        "--force",
        "--options",
        "runtime",
        "--timestamp",
        "--entitlements",
        str(entitlements),
        "--sign",
        identity,
    ]
    files = sorted(macho_files, key=lambda path: (len(path.parts), str(path)), reverse=True)
    cmds = [[*common, str(path)] for path in files]
    cmds.append([*common, str(app)])
    return cmds


def productsign_command(src: Path, dest: Path, identity: str) -> list[str]:
    return ["productsign", "--timestamp", "--sign", identity, str(src), str(dest)]


def notarize_commands(pkg: Path, keychain_profile: str) -> List[List[str]]:
    return [
        [
            "xcrun",
            "notarytool",
            "submit",
            str(pkg),
            "--keychain-profile",
            keychain_profile,
            "--wait",
        ],
        ["xcrun", "stapler", "staple", str(pkg)],
    ]


def find_identities() -> SigningIdentities:
    override = SigningIdentities(
        application=os.environ.get("AUDIO_TOOLS_SIGN_APPLICATION") or None,
        installer=os.environ.get("AUDIO_TOOLS_SIGN_INSTALLER") or None,
    )
    if override.application or override.installer:
        return override
    try:
        output = subprocess.check_output(["security", "find-identity", "-v"], text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"warning: could not list signing identities: {exc}", file=sys.stderr)
        return SigningIdentities(None, None)
    return parse_identities(output)


def iter_macho(root: Path) -> List[Path]:
    found: List[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            with path.open("rb") as handle:
                magic = handle.read(4)
        except OSError:
            continue
        if magic in MACH_O_MAGICS:
            found.append(path)
    return found


def strip_quarantine(path: Path) -> None:
    if path.exists():
        subprocess.run(["xattr", "-cr", str(path)], check=False, capture_output=True)


def _require_notarize() -> bool:
    return os.environ.get("AUDIO_TOOLS_REQUIRE_NOTARIZE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _notary_submit_command(pkg: Path) -> Optional[List[str]]:
    profile = os.environ.get("AUDIO_TOOLS_NOTARY_PROFILE") or os.environ.get(
        "NOTARYTOOL_PROFILE"
    )
    if profile:
        return notarize_commands(pkg, keychain_profile=profile)[0]
    apple_id = os.environ.get("APPLE_ID")
    password = os.environ.get("APPLE_APP_PASSWORD") or os.environ.get("APPLE_PASSWORD")
    team_id = os.environ.get("APPLE_TEAM_ID")
    if apple_id and password and team_id:
        return [
            "xcrun",
            "notarytool",
            "submit",
            str(pkg),
            "--apple-id",
            apple_id,
            "--password",
            password,
            "--team-id",
            team_id,
            "--wait",
        ]
    key = os.environ.get("APP_STORE_CONNECT_API_KEY_PATH")
    key_id = os.environ.get("APP_STORE_CONNECT_KEY_ID")
    issuer = os.environ.get("APP_STORE_CONNECT_ISSUER_ID")
    if key and key_id and issuer:
        return [
            "xcrun",
            "notarytool",
            "submit",
            str(pkg),
            "--key",
            key,
            "--key-id",
            key_id,
            "--issuer",
            issuer,
            "--wait",
        ]
    return None


def sign_app(app: Path, identity: str, entitlements: Path) -> None:
    if not app.is_dir():
        raise FileNotFoundError(f"missing app bundle: {app}")
    if not entitlements.is_file():
        raise FileNotFoundError(f"missing entitlements: {entitlements}")
    macho = iter_macho(app)
    print(f"Signing {len(macho)} binaries in {app} as {identity}")
    for command in codesign_app_commands(app, identity, entitlements, macho):
        subprocess.run(command, check=True)
    strip_quarantine(app)


def sign_pkg(app: Path, pkg: Path) -> int:
    strip_quarantine(app)
    strip_quarantine(pkg)
    identities = find_identities()
    if not identities.can_distribute():
        print(_MISSING_DEVELOPER_ID, file=sys.stderr)
        return 1 if _require_notarize() else 0
    assert identities.application and identities.installer
    sign_app(app, identities.application, ENTITLEMENTS)
    signed = pkg.with_name(f"{pkg.stem}.signed.pkg")
    if signed.exists():
        signed.unlink()
    print(f"Signing installer as {identities.installer}")
    subprocess.run(productsign_command(pkg, signed, identities.installer), check=True)
    signed.replace(pkg)
    strip_quarantine(pkg)
    submit = _notary_submit_command(pkg)
    if submit is None:
        print(
            "Signed the .pkg but skipped notarization. Set "
            "AUDIO_TOOLS_NOTARY_PROFILE or APPLE_ID + APPLE_APP_PASSWORD + "
            "APPLE_TEAM_ID, then re-run signing. Gatekeeper still blocks "
            "downloaded copies until Apple notarizes the package.",
            file=sys.stderr,
        )
        return 1 if _require_notarize() else 0
    print(f"Submitting {pkg} to Apple notary service")
    subprocess.run(submit, check=True)
    subprocess.run(["xcrun", "stapler", "staple", str(pkg)], check=True)
    strip_quarantine(pkg)
    print(f"Notarized and stapled {pkg}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("identities", help="Print detected Developer ID identities")
    app_parser = sub.add_parser("sign-app", help="Codesign AudioTools.app")
    app_parser.add_argument("app", type=Path)
    pkg_parser = sub.add_parser("sign-pkg", help="Codesign app, productsign pkg, notarize")
    pkg_parser.add_argument("--app", type=Path, required=True)
    pkg_parser.add_argument("--pkg", type=Path, required=True)
    args = parser.parse_args(argv)

    if args.cmd == "identities":
        ids = find_identities()
        print(f"application={ids.application or ''}")
        print(f"installer={ids.installer or ''}")
        print(f"can_distribute={ids.can_distribute()}")
        return 0 if ids.can_distribute() or not _require_notarize() else 1
    if args.cmd == "sign-app":
        ids = find_identities()
        if not ids.application:
            print(_MISSING_DEVELOPER_ID, file=sys.stderr)
            return 1 if _require_notarize() else 0
        sign_app(args.app, ids.application, ENTITLEMENTS)
        return 0
    return sign_pkg(args.app, args.pkg)


if __name__ == "__main__":
    raise SystemExit(main())
