FROM python:3.13.15-slim-bookworm@sha256:2325bb286ec344af3e5898cc224b5844e2707ac6e26b1632516fd3edc84a5e26

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/tmp

# LightGBM'nin sabit Linux wheel'i OpenMP kitaplığına ihtiyaç duyar.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1=12.2.0-14+deb12u1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-linux.lock /opt/requirements-linux.lock
RUN python -m pip install --no-cache-dir --no-compile --only-binary=:all: \
        --require-hashes -r /opt/requirements-linux.lock \
    && python -m pip check

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid 10001 --no-create-home app \
    && mkdir -p /app/config /app/data/ml/golge \
    && chown -R 10001:10001 /app

WORKDIR /app
COPY requirements-linux.lock requirements-linux.lock
COPY --chown=10001:10001 app/ app/
COPY --chown=10001:10001 tools/docker_entrypoint.py tools/docker_entrypoint.py
COPY scripts/api_okuma_rolu.sql scripts/api_okuma_rolu.sql
# Ön kayıt yalnız uyumluluk doğrulaması içindir; çalışma ayarları paketten gelir.
COPY config/shadow.json /opt/delivery/shadow.json

USER 10001:10001
ENTRYPOINT ["python", "/app/tools/docker_entrypoint.py"]
CMD ["python", "--version"]
