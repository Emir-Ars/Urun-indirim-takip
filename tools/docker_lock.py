"""Linux pip raporunu hash zorunlu kurulum girdisine dönüştürür; paket kurmaz."""

import argparse
import hashlib
import json
import re
import tomllib
from pathlib import Path
from urllib.parse import urlsplit

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

PROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def requirements_input(project):
    values = project["dependencies"][:]
    for extra in ("web", "ml"):
        values.extend(project["optional-dependencies"][extra])
    return "\n".join(values) + "\n"


def lock_text(report, project):
    environment = report["environment"]
    if report["version"] != "1" or any(
        environment[key] != value
        for key, value in {
            "python_full_version": "3.13.15",
            "implementation_name": "cpython",
            "platform_machine": "x86_64",
            "sys_platform": "linux",
        }.items()
    ):
        raise ValueError("Rapor Python 3.13.15 / Linux x86_64 ortamından olmalı.")
    packages = {}
    for item in report["install"]:
        name = canonicalize_name(item["metadata"]["name"])
        version = item["metadata"]["version"]
        download = item["download_info"]
        digest = download.get("archive_info", {}).get("hashes", {}).get("sha256", "")
        if (
            name in packages
            or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name)
            or not re.fullmatch(r"[0-9][a-zA-Z0-9.!+_-]*", version)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or not urlsplit(download["url"]).path.endswith(".whl")
            or item.get("is_direct")
            or item.get("is_yanked")
        ):
            raise ValueError(
                "Rapor tekil, hash'li ve yayımdan çekilmemiş wheel içermeli."
            )
        extras = sorted(item.get("requested_extras", []))
        if any(
            not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", extra) for extra in extras
        ):
            raise ValueError("Paket ek özelliği geçersiz.")
        packages[name] = (version, digest, extras)
    source = requirements_input(project)
    for line in source.splitlines():
        requirement = Requirement(line)
        if requirement.marker and not requirement.marker.evaluate(environment):
            continue
        value = packages.get(canonicalize_name(requirement.name))
        if value is None or value[0] not in requirement.specifier:
            raise ValueError("Rapor pyproject.toml bağımlılıklarıyla uyuşmuyor.")
        if not requirement.extras.issubset(value[2]):
            raise ValueError("Rapor gerekli paket ek özelliklerini içermiyor.")
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    lines = [
        "# Python 3.13.15 / Linux x86_64 için seçilen wheel dosyaları.",
        "# Windows ortamına kurulmaz; yenileme komutları docs/teknik.md içindedir.",
        f"# Bağımlılık girdisi SHA-256: {digest}",
        f"# Çözümleyici: pip {report['pip_version']}",
        "",
    ]
    for name, (version, digest, extras) in sorted(packages.items()):
        suffix = "[" + ",".join(extras) + "]" if extras else ""
        lines.append(f"{name}{suffix}=={version} \\")
        lines.append(f"    --hash=sha256:{digest}")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("input", "lock"):
        command = commands.add_parser(name)
        command.add_argument("--output", type=Path, required=True)
        if name == "lock":
            command.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    project = tomllib.loads(PROJECT.read_text(encoding="utf-8"))["project"]
    if args.command == "input":
        content = requirements_input(project)
    else:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        content = lock_text(report, project)
    args.output.write_text(content, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
