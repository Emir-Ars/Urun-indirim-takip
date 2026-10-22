"""Yerel API testlerinin sahte havuzu ve TestClient fixture'ları."""

import os
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app.api import database, main
from app.database import read


class FakePool:
    def __init__(self):
        self.opened = self.closed = self.borrowed = self.returned = 0
        self.failure = None
        self.conn = object()

    def open(self, *, wait):
        assert wait is False
        self.opened += 1

    def close(self):
        self.closed += 1

    @contextmanager
    def connection(self):
        if self.failure:
            raise self.failure
        self.borrowed += 1
        try:
            yield self.conn
        finally:
            self.returned += 1


@pytest.fixture
def stub(monkeypatch):
    pool = FakePool()
    monkeypatch.setattr(database, "create_pool", lambda: pool)
    monkeypatch.setattr(database, "validate_readiness", lambda conn: None)
    monkeypatch.setattr(read, "list_products", lambda conn: ())
    monkeypatch.setattr(
        read, "read_run_status", lambda conn: read.RunStatus(None, None)
    )
    monkeypatch.setattr(read, "read_product", lambda *args: None)
    with TestClient(main.create_app(), raise_server_exceptions=False) as client:
        yield pool, client
    assert pool.opened == pool.closed == 1
    assert pool.borrowed == pool.returned


@pytest.fixture
def client(world, monkeypatch):
    monkeypatch.setenv("API_DATABASE_URL", os.environ["TEST_API_DATABASE_URL"])
    app = main.create_app()
    with TestClient(app, raise_server_exceptions=False) as result:
        yield result
    assert app.state.pool.closed
