"""PowerShell teslim yöneticisinin seçim ve hata kurtarma sözleşmesi."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "case",
    [
        "selection",
        "bad_selection",
        "same_package",
        "stopped_switch",
        "running_switch",
        "failed_switch",
        "failed_recovery",
        "failed_selection_write",
        "healthy_start",
        "recreate_pair",
        "check_failure",
        "port_conflict",
        "record_integrity",
        "environment",
        "logs",
        "half_prepared",
        "exclusive_action",
    ],
)
def test_delivery_controller(case, tmp_path):
    shell = shutil.which("pwsh") or shutil.which("powershell.exe")
    assert shell, "Teslim komutu testleri için PowerShell gerekli."
    result = subprocess.run(
        [
            shell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "tests/support/delivery_cli.ps1"),
            "-Case",
            case,
            "-Root",
            str(tmp_path),
        ],
        capture_output=True,
        encoding="utf-8-sig",
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK:" + case in result.stdout


def test_delivery_powershell_files_have_bom():
    for name in ("teslim", "teslim_ortak", "teslim_paket", "teslim_hazirla"):
        assert (ROOT / f"scripts/{name}.ps1").read_bytes().startswith(b"\xef\xbb\xbf")


@pytest.mark.parametrize(
    "args",
    [
        ["-Action", "Start", "-Bundle", "unused"],
        ["-Action", "Prepare"],
        ["-Action", "Stop", "-Lines", "5"],
        ["-Action", "Export", "-Image", "unused:image"],
    ],
)
def test_invalid_action_options_fail_before_docker(args):
    shell = shutil.which("pwsh") or shutil.which("powershell.exe")
    assert shell, "Teslim komutu testleri için PowerShell gerekli."
    result = subprocess.run(
        [
            shell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts/teslim.ps1"),
            *args,
        ],
        capture_output=True,
        encoding="utf-8-sig",
        timeout=15,
    )
    assert result.returncode == 1
    assert "Bundle yalnız Prepare" in result.stdout
    assert "Docker" not in result.stdout + result.stderr
