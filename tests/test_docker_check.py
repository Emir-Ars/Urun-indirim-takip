"""Docker kabul aracının canlı adres ve mevcut çıktı alanını kullanmaması."""

import base64
import json
from types import SimpleNamespace

import pytest

from tools import docker_check


@pytest.fixture
def check(tmp_path, monkeypatch):
    (tmp_path / "compose.yaml").write_text("services: {}\n", encoding="utf-8")
    monkeypatch.setattr(docker_check, "ROOT", tmp_path)
    output = docker_check.new_output(tmp_path / "artifacts/check")
    return docker_check.DockerCheck(output, "default")


def test_output_rejects_existing_and_external_directories(tmp_path, monkeypatch):
    monkeypatch.setattr(docker_check, "ROOT", tmp_path)
    existing = tmp_path / "artifacts/existing"
    existing.mkdir(parents=True)
    marker = existing / "keep"
    marker.write_text("existing")
    for target in (existing, tmp_path / "outside"):
        with pytest.raises(ValueError):
            docker_check.new_output(target)
    assert marker.read_text() == "existing"
    assert not (tmp_path / "outside").exists()


def test_docker_does_not_receive_live_environment(check, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "private-live-url")
    monkeypatch.setenv("API_DATABASE_URL", "private-reader-url")
    monkeypatch.setenv("PGPASSWORD", "private-password")
    monkeypatch.setenv("DOCKER_HOST", "tcp://foreign:2375")
    fresh = docker_check.DockerCheck(check.output / "other", "default")

    def run(command, **kwargs):
        assert command[:3] == ["docker", "--context", "default"]
        assert not any(
            key in kwargs["env"]
            for key in ("DATABASE_URL", "API_DATABASE_URL", "PGPASSWORD", "DOCKER_HOST")
        )
        return SimpleNamespace(returncode=0, stdout=b"ok", stderr=b"")

    monkeypatch.setattr(docker_check.subprocess, "run", run)
    assert fresh.docker("info") == "ok"


def test_foreign_engine_is_rejected_before_build(check, monkeypatch):
    calls = []

    def docker(*args, **kwargs):
        calls.append(args)
        return "tcp://foreign:2375"

    monkeypatch.setattr(check, "docker", docker)
    with pytest.raises(ValueError):
        check.source()
    assert len(calls) == 1


def test_failure_diagnostic_masks_generated_secrets(check, monkeypatch):
    check.private_values = ["fake-sensitive"]
    monkeypatch.setattr(
        docker_check.subprocess,
        "run",
        lambda *a, **kw: SimpleNamespace(
            returncode=1, stdout=b"fake-sensitive", stderr=b"error"
        ),
    )
    with pytest.raises(RuntimeError):
        check.docker("info")
    diagnostic = (check.output / "failure.log").read_text()
    assert "fake-sensitive" not in diagnostic
    assert "[gizli]" in diagnostic


def test_probe_uses_process_tmp_with_namespace_test_package(check, monkeypatch):
    support = docker_check.ROOT / "tests/support"
    support.mkdir(parents=True)
    (support / "docker_probe.py").write_bytes(b"print('probe')")
    calls = []
    monkeypatch.setattr(check, "compose", lambda *a, **kw: "fake-container")

    def docker(*args, **kwargs):
        assert args[:3] == ("exec", "-i", "fake-container")
        payload = json.loads(kwargs["input_data"])
        assert payload["tests/__init__.py"] == ""
        assert base64.b64decode(payload["tests/support/docker_probe.py"]) == (
            b"print('probe')"
        )
        calls.append(args)

    monkeypatch.setattr(check, "docker", docker)
    check.install_probes({})
    assert len(calls) == 2
