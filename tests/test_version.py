import tomllib
from pathlib import Path

import api
from tests.conftest import auth_get

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.0.1"


def test_package_declares_the_release_version():
    assert api.__version__ == VERSION


def test_pyproject_version_matches_the_package():
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text())

    assert metadata["project"]["version"] == api.__version__


def test_openapi_reports_the_package_version(client):
    assert auth_get(client, "/openapi.json").json()["info"]["version"] == api.__version__


def test_header_badge_shows_the_package_version(client):
    html = auth_get(client, "/web").text
    badge = html.split('class="brand-version"', 1)[1].split(">", 1)[1].split("<", 1)[0]

    assert badge.strip() == f"v{api.__version__}"


def test_changelog_documents_the_release():
    changelog = (ROOT / "CHANGELOG.md").read_text()

    assert f"## [{VERSION}]" in changelog


def test_reload_is_off_unless_the_environment_asks_for_it(monkeypatch):
    from api.config import Settings

    monkeypatch.setenv("TSYNCER_BASIC_USER", "u")
    monkeypatch.setenv("TSYNCER_BASIC_PASSWORD", "p")

    assert Settings(_env_file=None).reload is False
