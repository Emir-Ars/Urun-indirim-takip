"""Yanlış platformun veya doğrulanmamış paketin Linux kilidine girmemesi."""

import hashlib
import re
import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from tools import docker_lock

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def resolution():
    project = {
        "dependencies": ["demo[feature]>=1.0"],
        "optional-dependencies": {"web": ["widget==2.0"], "ml": []},
    }
    report = {
        "version": "1",
        "pip_version": "26.2.1",
        "environment": {
            "python_full_version": "3.13.15",
            "implementation_name": "cpython",
            "platform_machine": "x86_64",
            "sys_platform": "linux",
        },
        "install": [
            {
                "metadata": {"name": name, "version": version},
                "requested_extras": extras,
                "download_info": {
                    "url": f"https://files.pythonhosted.org/{name}.whl",
                    "archive_info": {"hashes": {"sha256": "a" * 64}},
                },
            }
            for name, version, extras in [
                ("widget", "2.0", []),
                ("demo", "1.2", ["feature"]),
            ]
        ],
    }
    return report, project


def test_lock_pins_hashes_extras_and_input_fingerprint(resolution):
    report, project = resolution
    text = docker_lock.lock_text(report, project)
    assert "demo[feature]==1.2" in text
    assert "widget==2.0" in text
    assert text.count("--hash=sha256:" + "a" * 64) == 2
    source = b"demo[feature]>=1.0\nwidget==2.0\n"
    assert hashlib.sha256(source).hexdigest() in text
    assert text.index("demo[feature]") < text.index("widget==")


@pytest.mark.parametrize(
    "field,value",
    [
        ("python_full_version", "3.13.16"),
        ("implementation_name", "pypy"),
        ("platform_machine", "aarch64"),
        ("sys_platform", "win32"),
    ],
)
def test_lock_rejects_other_runtime(resolution, field, value):
    report, project = resolution
    report["environment"][field] = value
    with pytest.raises(ValueError):
        docker_lock.lock_text(report, project)


@pytest.mark.parametrize(
    "fault", ["duplicate", "hash", "source", "yanked", "direct", "extras", "version"]
)
def test_lock_rejects_unverified_or_incompatible_packages(resolution, fault):
    report, project = resolution
    item = report["install"][1]
    if fault == "duplicate":
        report["install"].append(item)
    elif fault == "hash":
        item["download_info"]["archive_info"]["hashes"]["sha256"] = "invalid"
    elif fault == "source":
        item["download_info"]["url"] = "https://files.pythonhosted.org/demo.tar.gz"
    elif fault == "yanked":
        item["is_yanked"] = True
    elif fault == "direct":
        item["is_direct"] = True
    elif fault == "extras":
        item["requested_extras"] = []
    else:
        item["metadata"]["version"] = "0.1"
    with pytest.raises(ValueError):
        docker_lock.lock_text(report, project)


def test_committed_lock_matches_runtime_requirements():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    content = (ROOT / "requirements-linux.lock").read_text(encoding="utf-8")
    digest = hashlib.sha256(
        docker_lock.requirements_input(project).encode("utf-8")
    ).hexdigest()
    assert digest in content
    lines = content.splitlines()
    locked = {}
    for index, line in enumerate(lines):
        if not line or line.startswith("#") or line.startswith(" "):
            continue
        requirement = Requirement(line.removesuffix(" \\"))
        pins = list(requirement.specifier)
        assert len(pins) == 1 and pins[0].operator == "=="
        assert re.fullmatch(r"    --hash=sha256:[0-9a-f]{64}", lines[index + 1])
        name = canonicalize_name(requirement.name)
        assert name not in locked
        locked[name] = (pins[0].version, requirement.extras)
    for value in docker_lock.requirements_input(project).splitlines():
        requirement = Requirement(value)
        version, extras = locked[canonicalize_name(requirement.name)]
        assert version in requirement.specifier
        assert requirement.extras.issubset(extras)
