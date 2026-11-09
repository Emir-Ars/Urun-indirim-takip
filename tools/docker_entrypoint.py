"""Docker API parolasını geçici pgpass dosyasına alır ve süreci devreder."""

import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

API_SECRET = Path("/run/secrets/api_password")


def prepare_api_passfile(url, secret_path, directory=None):
    parsed = urlsplit(url)
    database = parsed.path.removeprefix("/")
    user = (
        "fiyat_takip_api"
        if database == "fiyat_takip"
        else (
            "fiyat_takip_api_test"
            if re.fullmatch(r"[a-z][a-z0-9_]*_test", database)
            else None
        )
    )
    if (
        parsed.scheme != "postgresql"
        or parsed.hostname != "db"
        or parsed.port != 5432
        or user is None
        or parsed.username != user
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Docker API bağlantısı teslim sözleşmesine uymuyor.")
    password = Path(secret_path).read_text(encoding="utf-8").removesuffix("\n")
    if not password or any(value in password for value in ("\r", "\n", "\0")):
        raise ValueError("Docker API parola dosyası geçersiz.")
    escaped = password.replace("\\", "\\\\").replace(":", "\\:")
    descriptor, name = tempfile.mkstemp(prefix="api-pgpass-", dir=directory)
    path = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(f"db:5432:{database}:{user}:{escaped}\n")
        os.chmod(path, 0o600)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "--api":
        arguments.pop(0)
        try:
            path = prepare_api_passfile(os.getenv("API_DATABASE_URL", ""), API_SECRET)
        except (OSError, ValueError):
            # Ham dosya/URL hatası parolayı çıktıya taşıyabilir.
            print("Docker API parola hazırlığı tamamlanamadı.", file=sys.stderr)
            return 1
        os.environ["PGPASSFILE"] = str(path)
    if not arguments:
        print("Konteynerde çalıştırılacak komut gerekli.", file=sys.stderr)
        return 2
    try:
        os.execvp(arguments[0], arguments)
    except OSError:
        print("Konteyner komutu başlatılamadı.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
