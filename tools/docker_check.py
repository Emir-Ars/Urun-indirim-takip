"""Yalnız üretilmiş _test verisiyle yerel/CI Docker teslim kabulü."""

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import traceback
import urllib.request
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
DATABASE = "teslim_kabul_test"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def new_output(path):
    path = path.resolve()
    if not path.is_relative_to(ROOT / "artifacts") or path.exists():
        raise ValueError("Çıktı artifacts altında yeni bir klasör olmalı.")
    path.mkdir(parents=True, mode=0o700)
    return path


class DockerCheck:
    def __init__(self, output, context):
        self.output, self.context = output, context
        self.run_id = uuid4().hex[:12]
        self.image = "fiyat-takip-teslim:check-" + self.run_id
        self.synthetic_image = self.image + "-synthetic"
        self.projects, self.checks = [], []
        self.private_values = []
        self.environment = {
            key: value
            for key, value in os.environ.items()
            if key not in ("DATABASE_URL", "API_DATABASE_URL", "DOCKER_HOST")
            and not key.startswith(("PG", "DELIVERY_"))
        }
        self.fixture = output / "fixture"
        (self.fixture / "package").mkdir(parents=True)
        self.compose_file = output / "compose.check.yaml"
        self.offline_file = output / "compose.offline.yaml"
        self.compose_file.write_text(
            (ROOT / "compose.yaml").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        self.offline_file.write_text(
            self.compose_file.read_text(encoding="utf-8")
            + "\nnetworks:\n  default:\n    internal: true\n",
            encoding="utf-8",
        )

    def docker(self, *arguments, expected=0, binary=False, input_data=None):
        result = subprocess.run(
            ["docker", "--context", self.context, *map(str, arguments)],
            capture_output=True,
            env=self.environment,
            timeout=900,
            input=input_data,
        )
        if result.returncode != expected:
            diagnostic = (result.stdout + result.stderr).decode(
                "utf-8", errors="replace"
            )
            for value in self.private_values:
                diagnostic = diagnostic.replace(value, "[gizli]")
            (self.output / "failure.log").write_text(diagnostic, encoding="utf-8")
            raise RuntimeError(
                "Docker kabul adımı başarısız; gizli çıktı gösterilmedi."
            )
        return result.stdout if binary else result.stdout.decode("utf-8-sig").strip()

    def compose(self, project, *arguments, expected=0):
        saved = self.environment.copy()
        self.environment.update(project["environment"])
        try:
            return self.docker(
                "compose",
                "--project-directory",
                ROOT,
                "-f",
                self.compose_file,
                "-p",
                project["name"],
                *arguments,
                expected=expected,
            )
        finally:
            self.environment = saved

    def project(self, suffix, image):
        state = self.output / suffix
        private = state / "secrets"
        private.mkdir(parents=True, mode=0o700)
        for name in ("admin_password", "api_password"):
            path = private / name
            value = secrets.token_hex(32)
            self.private_values.append(value)
            path.write_text(value, encoding="utf-8")
            # Ana dizin 0700; Compose bind sırrını konteynerde 10001 okuyabilmeli.
            path.chmod(0o644)
        project = dict(
            name="delivery-check-" + self.run_id + "-" + suffix,
            environment=dict(
                DELIVERY_STATE_DIR=str(state),
                DELIVERY_BUNDLE_DIR=str(self.fixture / "package"),
                DELIVERY_DATABASE=DATABASE,
                DELIVERY_API_USER="fiyat_takip_api_test",
                DELIVERY_IMAGE=image,
            ),
        )
        self.projects.append(project)
        return project

    def checked(self, name):
        self.checks.append(name)
        print("Doğrulandı: " + name, flush=True)

    def helper(self, project, module, *arguments):
        user = f"{os.getuid()}:{os.getgid()}" if os.name == "posix" else "10001:10001"
        return self.compose(
            project,
            "run",
            "--rm",
            "--no-deps",
            "--pull",
            "never",
            "-T",
            "--user",
            user,
            "-v",
            f"{ROOT / 'tests'}:/app/tests:ro",
            "-v",
            f"{self.fixture}:/fixture",
            "transfer",
            "python",
            "-m",
            module,
            *arguments,
        )

    def probe(self, project, service, mode):
        return self.compose(
            project,
            "exec",
            "-T",
            "-e",
            "PYTHONPATH=/tmp",
            service,
            "python",
            "-m",
            "tests.support.docker_probe",
            mode,
        )

    def install_probes(self, project):
        payload = json.dumps(
            {
                "tests/__init__.py": "",
                "tests/support/__init__.py": "",
                "tests/support/docker_probe.py": base64.b64encode(
                    (ROOT / "tests/support/docker_probe.py").read_bytes()
                ).decode("ascii"),
            }
        ).encode()
        receiver = (
            "import base64,json,sys; from pathlib import Path; "
            "files=json.load(sys.stdin); "
            "[(p.parent.mkdir(parents=True,exist_ok=True),"
            "p.write_bytes(base64.b64decode(data))) "
            "for name,data in files.items() for p in [Path('/tmp')/name]]"
        )
        for service in ("api", "ui"):
            container = self.compose(project, "ps", "-q", service)
            self.docker(
                "exec", "-i", container, "python", "-c", receiver, input_data=payload
            )

    def health(self):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open("http://127.0.0.1:8503/_stcore/health", timeout=5) as response:
            assert response.status == 200 and response.read() == b"ok"

    def source(self):
        endpoint = self.docker(
            "context", "inspect", self.context, "--format", "{{.Endpoints.docker.Host}}"
        )
        allowed = (
            "npipe:////./pipe/dockerDesktopLinuxEngine",
            "unix:///var/run/docker.sock",
        )
        if endpoint not in allowed:
            raise ValueError("Kabul yalnız yerel Docker motorunda çalışır.")
        if self.docker("info", "--format", "{{.OSType}}") != "linux":
            raise ValueError("Linux konteynerleri gerekli.")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 8503))
        print("Kabul imajı oluşturuluyor.", flush=True)
        self.docker("build", "--file", ROOT / "Dockerfile", "--tag", self.image, ROOT)
        postgres = re.search(
            r"postgres:17\.11-bookworm@sha256:[0-9a-f]{64}",
            self.compose_file.read_text(),
        ).group()
        # İlk hazırlık internet kullanabilir; sonraki bütün açılışlar pull=never.
        self.docker("pull", "--platform", "linux/amd64", postgres)
        source = self.project("source", self.image)
        self.compose(source, "up", "-d", "--wait", "--wait-timeout", "120", "db")
        print("Yapay model, kayıtlar ve ayrı test kaynağı hazırlanıyor.", flush=True)
        self.helper(
            source, "tests.support.docker_fixture", "seed", "--output", "/fixture"
        )
        dump = self.compose_dump(source)
        (self.fixture / "package/database.dump").write_bytes(dump)
        self.helper(
            source, "tests.support.docker_fixture", "seal", "--output", "/fixture"
        )
        manifest = json.loads((self.fixture / "package/manifest.json").read_bytes())
        assert manifest["database"]["name"] == DATABASE
        context = self.output / "synthetic_image"
        context.mkdir()
        shutil.copyfile(
            self.fixture / "build/source/config/shadow.json", context / "shadow.json"
        )
        (context / "Dockerfile").write_text(
            f"FROM {self.image}\nCOPY shadow.json /opt/delivery/shadow.json\n",
            encoding="utf-8",
        )
        self.docker(
            "build", "--network", "none", "--tag", self.synthetic_image, context
        )
        self.compose(source, "stop", "db")
        self.checked("Yapay kaynak ve tutarlı PostgreSQL 17 arşivi")

    def compose_dump(self, project):
        saved = self.environment.copy()
        self.environment.update(project["environment"])
        try:
            return self.docker(
                "compose",
                "--project-directory",
                ROOT,
                "-f",
                self.compose_file,
                "-p",
                project["name"],
                "exec",
                "-T",
                "--user",
                "postgres",
                "db",
                "pg_dump",
                "--username=postgres",
                "--dbname=" + DATABASE,
                "--format=custom",
                "--no-owner",
                "--no-privileges",
                "--schema=public",
                binary=True,
            )
        finally:
            self.environment = saved

    def verify(self, package, expected=0):
        return self.docker(
            "run",
            "--rm",
            "--pull",
            "never",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:mode=1777",
            "--mount",
            f"type=bind,source={package},target=/bundle,readonly",
            self.synthetic_image,
            "python",
            "-m",
            "app.delivery",
            "verify",
            "--bundle",
            "/bundle",
            expected=expected,
        )

    def reject(self):
        original = self.fixture / "package"
        for kind in ("missing", "hash", "model", "schema"):
            bad = self.output / ("rejected_" + kind)
            shutil.copytree(original, bad)
            manifest = json.loads((bad / "manifest.json").read_bytes())
            if kind == "missing":
                (bad / "config/runtime.json").unlink()
            elif kind == "hash":
                (bad / "config/runtime.json").write_text('{"broken":true}')
            elif kind == "model":
                manifest["model_manifest_sha256"] = "0" * 64
            else:
                manifest["database"]["schema_sha256"] = "0" * 64
            (bad / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            self.verify(bad, expected=1)
        self.checked("Eksik/bozuk dosya, yabancı model ve şema reddi")

    def target(self):
        target = self.project("target", self.synthetic_image)
        self.verify(self.fixture / "package")
        self.compose(
            target,
            "up",
            "-d",
            "--no-build",
            "--pull",
            "never",
            "--wait",
            "--wait-timeout",
            "120",
            "db",
        )
        transfer = (
            "run",
            "--rm",
            "--no-deps",
            "--pull",
            "never",
            "-T",
            "transfer",
            "python",
            "-m",
            "app.delivery",
        )
        self.compose(target, *transfer, "bootstrap", "--bundle", "/bundle")
        container = self.compose(target, "ps", "-q", "db")
        self.docker(
            "cp", self.fixture / "package/database.dump", container + ":/tmp/check.dump"
        )
        self.docker(
            "exec",
            "--user",
            "postgres",
            container,
            "pg_restore",
            "--username=postgres",
            "--dbname=" + DATABASE,
            "--no-owner",
            "--no-privileges",
            "--role=fiyat_takip_owner",
            "--single-transaction",
            "--exit-on-error",
            "/tmp/check.dump",
        )
        self.compose(target, *transfer, "finalize", "--bundle", "/bundle")
        self.compose(target, *transfer, "check", "--bundle", "/bundle")
        self.checked("Boş hedefe kurulum; veri/şema/dosya ve okuma rolü eşleşmesi")
        self.open(target)
        self.install_probes(target)
        self.probe(target, "api", "reader")
        self.probe(target, "ui", "runtime")
        self.checked("Host HTTP, grafikler, bildirim ve SELECT sınırı")
        before = self.compose(target, "ps", "-q", "db", "api", "ui")
        self.compose(target, *transfer, "check", "--bundle", "/bundle")
        self.open(target)
        assert self.compose(target, "ps", "-q", "db", "api", "ui") == before
        self.checked("Aynı kopyanın tekrar kontrol/açılışında konteynerlerin korunması")
        self.compose(target, "stop", "db")
        self.probe(target, "ui", "unavailable")
        self.open(target)
        self.compose(target, "stop", "api")
        self.probe(target, "ui", "unavailable")
        self.compose(target, "stop", "ui", "api")
        self.compose(
            target,
            "up",
            "-d",
            "--no-deps",
            "--no-build",
            "--pull",
            "never",
            "--force-recreate",
            "--wait",
            "--wait-timeout",
            "120",
            "api",
            "ui",
        )
        self.health()
        self.checked("DB/API kesintisi ve API–UI birlikte yenileme")
        self.compose(target, "down")
        self.open(target)
        self.compose(target, *transfer, "check", "--bundle", "/bundle")
        self.checked("Konteynerler kaldırılıp açıldığında kalıcı verinin korunması")
        self.helper(target, "tests.support.docker_probe", "gate")
        self.checked(
            "Linux'ta erken kapı reddi, kesin açma/kapatma ve eski oranın gizlenmesi"
        )
        self.compose(target, "down")
        self.compose_file = self.offline_file
        self.open(target, host=False)
        self.install_probes(target)
        self.probe(target, "ui", "offline")
        self.checked("Dışa kapalı ağda yeniden açılış, gerçek HTTP ve grafikler")

    def open(self, project, host=True):
        self.compose(
            project,
            "up",
            "-d",
            "--no-build",
            "--pull",
            "never",
            "--wait",
            "--wait-timeout",
            "180",
            "db",
            "api",
            "ui",
        )
        if host:
            self.health()

    def run(self):
        status = "failed"
        try:
            self.source()
            self.reject()
            self.target()
            status = "passed"
        finally:
            for project in reversed(self.projects):
                try:
                    self.compose(project, "stop")
                except (RuntimeError, subprocess.TimeoutExpired):
                    status = "failed"
            report = dict(
                status=status,
                synthetic=True,
                database=DATABASE,
                checks=self.checks,
                bundle=str(self.fixture / "package"),
                image=self.synthetic_image,
                isolated_network=(self.compose_file == self.offline_file),
                physical_windows_machine=False,
            )
            (self.output / "report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        if status != "passed":
            raise RuntimeError("Docker kabulü tamamlanmadı.")


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--context", default="desktop-linux" if os.name == "nt" else "default"
    )
    args = parser.parse_args(argv)
    check = None
    try:
        check = DockerCheck(new_output(args.output), args.context)
        check.run()
    except (
        OSError,
        ValueError,
        RuntimeError,
        AssertionError,
        subprocess.SubprocessError,
    ):
        if check and not (check.output / "failure.log").exists():
            diagnostic = traceback.format_exc()
            for value in check.private_values:
                diagnostic = diagnostic.replace(value, "[gizli]")
            (check.output / "failure.log").write_text(diagnostic, encoding="utf-8")
        print(
            "Docker kabulü tamamlanmadı; rapordaki son başarılı adımı kontrol edin.",
            file=sys.stderr,
        )
        return 1
    print("Docker kabulü başarılı. Rapor: " + str(args.output / "report.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
