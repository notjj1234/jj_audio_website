"""Home component build is committed and path-free."""

from __future__ import annotations

from pathlib import Path


def test_home_build_is_committed():
    from ui.home_component import home_build_is_complete

    build = (
        Path(__file__).resolve().parents[1] / "ui" / "home_component" / "frontend" / "build"
    )
    assert (build / "index.html").is_file()
    assert list((build / "assets").glob("index-*.js"))
    assert home_build_is_complete(build), (
        "Home frontend is incomplete. Run scripts/dev.sh home-build"
    )


def test_home_build_is_complete_rejects_html_without_assets(tmp_path: Path):
    from ui.home_component import home_build_is_complete

    (tmp_path / "index.html").write_text(
        '<script type="module" src="./assets/index-missing.js"></script>',
        encoding="utf-8",
    )
    assert home_build_is_complete(tmp_path) is False


def test_home_package_has_no_extra_runtime_deps():
    text = (
        Path(__file__).resolve().parents[1]
        / "ui"
        / "home_component"
        / "frontend"
        / "package.json"
    ).read_text(encoding="utf-8")
    assert "streamlit-component-lib" in text
    assert '"vite"' in text
    assert "react" not in text.lower()
