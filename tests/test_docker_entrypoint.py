"""Docker girişinde parolanın ve bağlantı sınırının korunması."""

import os
import stat

import pytest

from tools import docker_entrypoint as entry


@pytest.mark.parametrize(
    "database,user",
    [("fiyat_takip", "fiyat_takip_api"), ("fiyat_takip_test", "fiyat_takip_api_test")],
)
def test_passfile_escapes_password_and_uses_only_docker_database(
    tmp_path, database, user
):
    secret = tmp_path / "secret"
    secret.write_text("a:b\\c\n", encoding="utf-8")
    path = entry.prepare_api_passfile(
        f"postgresql://{user}@db:5432/{database}", secret, tmp_path
    )
    assert path.read_text(encoding="utf-8") == f"db:5432:{database}:{user}:a\\:b\\\\c\n"
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://fiyat_takip_api@localhost:5432/fiyat_takip",
        "postgresql://fiyat_takip_api@host.docker.internal:5432/fiyat_takip",
        "postgresql://fiyat_takip_api:secret@db:5432/fiyat_takip",
        "postgresql://postgres@db:5432/fiyat_takip",
        "postgresql://fiyat_takip_api@db:5433/fiyat_takip",
        "postgresql://fiyat_takip_api@db:5432/other",
        "postgresql://fiyat_takip_api@db:5432/fiyat_takip?host=localhost",
        "postgresql://fiyat_takip_api@db:5432/fiyat_takip#other",
    ],
)
def test_passfile_rejects_production_hosts_and_connection_overrides(tmp_path, url):
    with pytest.raises(ValueError):
        entry.prepare_api_passfile(url, tmp_path / "missing", tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("password", ["", "a\nb", "a\0b", "a\rb"])
def test_invalid_secret_does_not_create_passfile(tmp_path, password):
    secret = tmp_path / "secret"
    secret.write_text(password, encoding="utf-8")
    with pytest.raises(ValueError):
        entry.prepare_api_passfile(
            "postgresql://fiyat_takip_api@db:5432/fiyat_takip", secret, tmp_path
        )
    assert list(tmp_path.iterdir()) == [secret]


def test_api_error_does_not_print_password_or_url(monkeypatch, capsys):
    marker = "private-password-marker"
    monkeypatch.setenv(
        "API_DATABASE_URL", f"postgresql://user:{marker}@db:5432/fiyat_takip"
    )
    assert entry.main(["--api", "python"]) == 1
    output = capsys.readouterr().err
    assert "hazırlığı" in output
    assert marker not in output
    assert "postgresql" not in output


def test_api_hands_private_passfile_to_process(monkeypatch, tmp_path):
    path = tmp_path / "passfile"
    monkeypatch.setenv("PGPASSFILE", "before-entrypoint")
    monkeypatch.setattr(entry, "prepare_api_passfile", lambda *args: path)

    def execute(command, arguments):
        assert command == "python"
        assert arguments == ["python", "-V"]
        assert os.environ["PGPASSFILE"] == str(path)
        raise SystemExit(0)

    monkeypatch.setattr(entry.os, "execvp", execute)
    with pytest.raises(SystemExit) as result:
        entry.main(["--api", "python", "-V"])
    assert result.value.code == 0


def test_ui_does_not_read_database_secret(monkeypatch):
    def unexpected(*args):
        pytest.fail("UI için parola hazırlanmamalı")

    def execute(command, arguments):
        assert arguments == ["python", "-V"]
        raise SystemExit(0)

    monkeypatch.setattr(entry, "prepare_api_passfile", unexpected)
    monkeypatch.setattr(entry.os, "execvp", execute)
    with pytest.raises(SystemExit):
        entry.main(["python", "-V"])
