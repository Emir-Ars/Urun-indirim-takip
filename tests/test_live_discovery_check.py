"""Manuel keşif aracının ham kanıt kaydı; bütün yanıtlar sahtedir."""

import json
from contextlib import contextmanager, nullcontext
from pathlib import Path

import pytest

from app.contracts import DiscoveryConfig, DiscoveryReport, DiscoveryTarget
from app.scrape_lock import ScrapeBusy
from app.scraper.http import FetchError, PageClient
from app.settings import Runtime
from tests.manual import live_discovery_check as manual
from tests.test_http import Recorder, Reply, page_client

URL = "https://www.trendyol.com/urun-p-123"


@pytest.mark.parametrize(
    "body,method,suffix",
    [
        (
            '<h1>Telefon</h1><link rel="canonical" href="/ürün">'.encode(),
            "get",
            ".html",
        ),
        (b'{ "id": 123, "pageUrl": "/urun-p-123" }\n', "get_json", ".json"),
    ],
)
def test_capture_keeps_source_bytes_and_does_not_repeat_request(
    tmp_path, body, method, suffix
):
    client = Recorder(Reply(content=body))
    pages = page_client(client)
    directory = tmp_path / "responses"
    manual._capture_responses(pages, directory)

    result = getattr(pages, method)(URL)

    assert result == (json.loads(body) if method == "get_json" else body.decode())
    index = json.loads((directory / "index.json").read_text(encoding="utf-8"))
    assert len(index) == len(client.calls) == pages.request_count == 1
    assert index[0]["url"] == URL and index[0]["method"] == "GET"
    assert index[0]["file"].endswith(suffix)
    assert (directory / index[0]["file"]).read_bytes() == body


def test_capture_preserves_retry_budget_and_does_not_invent_error_body(tmp_path):
    client = Recorder(Reply(status=503), Reply(content=b"{}"))
    pages = page_client(client, request_budget=2)
    directory = tmp_path / "responses"
    manual._capture_responses(pages, directory)

    assert pages.get_json(URL) == {}
    with pytest.raises(FetchError, match="istek sınırı") as error:
        pages.get(URL)

    assert error.value.code == "limit"
    index = json.loads((directory / "index.json").read_text(encoding="utf-8"))
    assert len(client.calls) == pages.request_count == 2
    assert index[0]["request_count"] == index[1]["request_count"] == 2
    assert index[1]["error_code"] == "limit" and "file" not in index[1]
    assert list(directory.glob("*.json")) == [
        directory / "0001.json",
        directory / "index.json",
    ]


def test_capture_retains_malformed_json_for_source_review(tmp_path):
    pages = page_client(Recorder(Reply(content=b'{"result":')))
    directory = tmp_path / "responses"
    manual._capture_responses(pages, directory)

    with pytest.raises(FetchError) as error:
        pages.get_json(URL)

    assert error.value.code == "parse"
    assert (directory / "0001.json").read_bytes() == b'{"result":'


@pytest.mark.parametrize("target", [None, "apple_iphone_15"])
def test_capture_requires_one_target_and_a_new_directory(tmp_path, monkeypatch, target):
    directory = tmp_path / "existing"
    directory.mkdir()
    marker = directory / "old.html"
    marker.write_bytes(b"previous evidence")
    monkeypatch.setattr(manual, "scrape_lock", nullcontext)
    monkeypatch.setattr(manual, "run", lambda **kw: pytest.fail("Tarama başlamamalı"))

    argv = ([] if target is None else [target]) + ["--save-responses", str(directory)]
    with pytest.raises(SystemExit) as error:
        manual.main(argv)

    assert error.value.code == 2
    assert marker.read_bytes() == b"previous evidence"
    assert list(directory.iterdir()) == [marker]


def test_capture_busy_lock_does_not_create_directory_or_start_scan(
    tmp_path, monkeypatch
):
    @contextmanager
    def busy():
        raise ScrapeBusy("Test kilidi meşgul")
        yield

    directory = tmp_path / "responses"
    monkeypatch.setattr(manual, "scrape_lock", busy)
    monkeypatch.setattr(manual, "run", lambda **kw: pytest.fail("Tarama başlamamalı"))

    assert manual.main(["apple_iphone_15", "--save-responses", str(directory)]) == 3
    assert not directory.exists()


def test_capture_cli_uses_dry_run_separate_report_and_trace(
    tmp_path, monkeypatch, capsys
):
    directory = tmp_path / "responses"
    calls = []
    report = DiscoveryReport(complete=False, dry_run=True, results=[])

    def fake_run(**kwargs):
        calls.append(kwargs)
        return report

    def adapters(traces, response_dir=None):
        assert response_dir == directory
        traces.append({"platform": "trendyol", "target_key": "apple_iphone_15"})
        return {"trendyol": object()}

    monkeypatch.setattr(manual, "scrape_lock", nullcontext)
    monkeypatch.setattr(manual, "traced_adapters", adapters)
    monkeypatch.setattr(manual, "run", fake_run)

    assert manual.main(["apple_iphone_15", "--save-responses", str(directory)]) == 2

    assert calls[0]["dry_run"] is True
    assert calls[0]["target_key"] == "apple_iphone_15"
    assert calls[0]["report_path"] == directory / "report.json"
    output = json.loads(capsys.readouterr().out)
    assert output["traces"] and output["responses"] == str(directory)
    assert output["report"]["dry_run"] is True


def test_capture_disk_failure_stops_scan_instead_of_claiming_evidence_saved(
    tmp_path, monkeypatch
):
    pages = page_client(Recorder(Reply(content=b"{}")))
    manual._capture_responses(pages, tmp_path / "responses")

    def failed_write(*args, **kwargs):
        raise OSError("Test diski dolu")

    monkeypatch.setattr(type(tmp_path), "write_bytes", failed_write)
    with pytest.raises(OSError, match="diski dolu"):
        pages.get_json(URL)


def test_traced_adapters_capture_each_platform_in_its_own_directory(
    tmp_path, monkeypatch
):
    catalog = Path(__file__).parent / "fixtures" / "discovery" / "catalog.json"
    monkeypatch.setenv("CATALOG_PATH", str(catalog))

    def source(self, method, url, **kwargs):
        self.request_count += 1
        return b'{ "id": 123 }'

    monkeypatch.setattr(PageClient, "_request", source)
    target = DiscoveryTarget(key="apple_iphone_15", brand="Apple", model="iPhone 15")
    adapters = manual.traced_adapters([], response_dir=tmp_path)

    for platform, implementation in adapters.items():
        adapter = implementation(target, DiscoveryConfig(targets=[]), Runtime())
        try:
            assert adapter.get_json(URL) == {"id": 123}
            directory = tmp_path / f"{platform}_{target.key}"
            assert (directory / "0001.json").read_bytes() == b'{ "id": 123 }'
            assert json.loads((directory / "index.json").read_text())[0]["url"] == URL
        finally:
            adapter.close()
    assert len(adapters) == 2


@pytest.mark.parametrize("trace", [False, True])
def test_manual_cli_without_capture_keeps_existing_output(trace, monkeypatch, capsys):
    report = DiscoveryReport(complete=True, dry_run=True, results=[])
    monkeypatch.setattr(manual, "scrape_lock", nullcontext)
    monkeypatch.setattr(manual, "traced_adapters", lambda *args: {})

    def fake_run(**kwargs):
        assert kwargs["report_path"] is None
        assert kwargs["dry_run"] is True
        return report

    monkeypatch.setattr(manual, "run", fake_run)
    assert manual.main(["apple_iphone_15"] + (["--trace"] if trace else [])) == 0

    output = json.loads(capsys.readouterr().out)
    assert output == (
        {"report": report.model_dump(mode="json"), "traces": []}
        if trace
        else report.model_dump(mode="json")
    )
