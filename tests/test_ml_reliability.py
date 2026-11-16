"""reliability-chart komutu: rapordaki kovaların aynen çizilmesi ve korumalar."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

import pytest

from app.ml import reliability
from app.ml.__main__ import main

ROOT = Path(__file__).resolve().parents[1]
SVG = "{http://www.w3.org/2000/svg}"
# 16 Kasım gölge raporunun asıl sonucundaki kovalara benzer yapay değerler.
DEFAULT_BINS = {
    0: (97, 0.0827, 0.0),
    1: (371, 0.1448, 0.1078),
    2: (118, 0.2344, 0.3051),
    3: (16, 0.3271, 0.5),
    4: (1, 0.4041, 0.0),
}


def _bins(values=None):
    values = DEFAULT_BINS if values is None else values
    rows = []
    for index in range(10):
        count, mean, observed = values.get(index, (0, None, None))
        rows.append(
            dict(
                lower=index / 10,
                upper=(index + 1) / 10,
                count=count,
                mean_probability=mean,
                observed_rate=observed,
                low_support=count < 20,
            )
        )
    return rows


def _write_report(
    folder, kind="shadow", bins=None, rows=None, final_date=False, manifest_changes=None
):
    bins = _bins() if bins is None else bins
    rows = sum(item["count"] for item in bins) if rows is None else rows
    score = dict(rows=rows, calibration=bins, brier=0.11)
    if kind == "shadow":
        report = dict(
            input=dict(choice="r2_platt", last_closed_day="2026-11-15"),
            scores=dict(main=dict(r2_platt=score, r0=dict(rows=rows))),
            gate=dict(first_anchor="2026-10-27", last_anchor="2026-11-08"),
            final_date_matches=final_date,
        )
        manifest = dict(kind="shadow_evaluation", status="complete")
    else:
        report = dict(
            choice="r2_platt",
            scores=dict(r2_platt=score),
            reserved_test=dict(first_anchor="2026-09-03", last_anchor="2026-10-25"),
        )
        manifest = dict(test_opened=True, status="complete")
    manifest.update(manifest_changes or {})
    folder.mkdir(parents=True)
    raw = json.dumps(report, ensure_ascii=False).encode("utf-8")
    (folder / "report.json").write_bytes(raw)
    (folder / "report.md").write_text("rapor\n", encoding="utf-8")
    manifest.setdefault(
        "files", {"report.json": hashlib.sha256(raw).hexdigest(), "report.md": "x"}
    )
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return folder


def _fingerprint(folder):
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(folder.iterdir())
    }


def _run(report, output):
    return main(["reliability-chart", "--report", str(report), "--output", str(output)])


def test_shadow_chart_draws_every_filled_bin_exactly(tmp_path, capsys):
    # Klasör adındaki & işareti SVG'yi bozmamalı.
    report = _write_report(tmp_path / "degerlendirme_&_deneme")
    before = _fingerprint(report)
    output = tmp_path / "grafik" / "golge.svg"

    assert _run(report, output) == 0

    root = ElementTree.fromstring(output.read_bytes())
    circles = root.findall(f".//{SVG}circle[@class='bin']")
    bars = root.findall(f".//{SVG}rect[@class='bar']")
    assert [int(item.get("data-bin")) for item in circles] == [0, 1, 2, 3, 4]
    assert [int(item.get("data-bin")) for item in bars] == [0, 1, 2, 3, 4]
    for circle in circles:
        count, mean, observed = DEFAULT_BINS[int(circle.get("data-bin"))]
        assert int(circle.get("data-count")) == count
        assert float(circle.get("data-mean")) == mean
        assert float(circle.get("data-observed")) == observed
        low = count < 20
        assert circle.get("data-low-support") == str(low).lower()
        assert circle.get("fill") == ("#ffffff" if low else "#1f5fa8")
    texts = [item.text for item in root.iter(f"{SVG}text")]
    assert "Güvenilirlik diyagramı" in texts
    assert "Gölge değerlendirme · asıl sonuç, kendi verimiz · 603 satır" in texts
    assert (
        "Başlangıçlar 27 Ekim – 8 Kasım 2026 · son kapanmış gün 15 Kasım 2026" in texts
    )
    assert "Dondurulan model: R2 + Platt · ara rapor, yalnız bilgi" in texts
    assert _fingerprint(report) == before
    out = capsys.readouterr().out
    assert "çizilen kova: 5 (düşük destekli 2)" in out
    assert "Rapor ve model değişmedi" in out


def test_point_position_follows_probability_and_observed_rate(tmp_path):
    report = _write_report(tmp_path / "rapor")
    output = tmp_path / "golge.svg"
    assert _run(report, output) == 0

    root = ElementTree.fromstring(output.read_bytes())
    circle = root.find(f".//{SVG}circle[@data-bin='1']")
    # x: sol kenar 80 + olasılık × 460; y: üst kenar 120 + (1 − oran) × 460.
    assert circle.get("cx") == f"{80 + 0.1448 * 460:.2f}"
    assert circle.get("cy") == f"{120 + (1 - 0.1078) * 460:.2f}"
    bar = root.find(f".//{SVG}rect[@class='bar'][@data-bin='1']")
    assert float(bar.get("height")) == pytest.approx(60.0)


def test_reserved_test_chart_uses_its_own_title_and_period(tmp_path):
    report = _write_report(tmp_path / "ml_son_test", kind="final")
    output = tmp_path / "sakli.svg"
    assert _run(report, output) == 0

    texts = [
        item.text for item in ElementTree.parse(output).getroot().iter(f"{SVG}text")
    ]
    assert "Saklı test (Cimri) · 603 satır" in texts
    assert "Başlangıçlar 3 Eylül – 25 Ekim 2026" in texts
    assert "Dondurulan model: R2 + Platt · saklı test bir kez açıldı" in texts


def test_final_evaluation_snapshot_is_named_as_such(tmp_path):
    report = _write_report(tmp_path / "rapor", final_date=True)
    output = tmp_path / "kesin.svg"
    assert _run(report, output) == 0
    assert "5 Ocak 2027 kesin değerlendirme görüntüsü" in output.read_text(
        encoding="utf-8"
    )


def test_same_report_produces_identical_bytes(tmp_path):
    report = _write_report(tmp_path / "rapor")
    assert _run(report, tmp_path / "bir.svg") == 0
    assert _run(report, tmp_path / "iki.svg") == 0
    assert (tmp_path / "bir.svg").read_bytes() == (tmp_path / "iki.svg").read_bytes()


def test_existing_file_is_never_overwritten(tmp_path, capsys):
    report = _write_report(tmp_path / "rapor")
    output = tmp_path / "golge.svg"
    output.write_text("eski", encoding="utf-8")

    assert _run(report, output) == 1
    assert output.read_text(encoding="utf-8") == "eski"
    assert "dosya zaten var" in capsys.readouterr().err


def test_output_must_be_svg(tmp_path):
    report = _write_report(tmp_path / "rapor")
    output = tmp_path / "golge.png"
    assert _run(report, output) == 1
    assert not output.exists()


def test_chart_is_not_written_into_report_folder(tmp_path, capsys):
    report = _write_report(tmp_path / "rapor")
    before = _fingerprint(report)

    assert _run(report, report / "grafik.svg") == 1
    assert _fingerprint(report) == before
    assert "rapor klasörünün içine yazılmaz" in capsys.readouterr().err


def test_report_changed_after_manifest_is_rejected(tmp_path, capsys):
    report = _write_report(tmp_path / "rapor")
    text = (report / "report.json").read_text(encoding="utf-8")
    (report / "report.json").write_text(text.replace("0.5", "0.6"), encoding="utf-8")
    output = tmp_path / "golge.svg"

    assert _run(report, output) == 1
    assert not output.exists()
    assert "SHA-256 ile eşleşmiyor" in capsys.readouterr().err


@pytest.mark.parametrize(
    "changes, message",
    [
        (dict(status="partial"), "tamamlanmamış"),
        (dict(kind="shadow_prediction"), "Desteklenmeyen rapor"),
    ],
)
def test_incomplete_or_unsupported_report_is_rejected(
    tmp_path, capsys, changes, message
):
    report = _write_report(tmp_path / "rapor", manifest_changes=changes)
    output = tmp_path / "golge.svg"
    assert _run(report, output) == 1
    assert not output.exists()
    assert message in capsys.readouterr().err


def _broken_bins(case):
    bins = _bins()
    if case == "sum":
        return bins, 604
    if case == "support":
        bins[3]["low_support"] = False
    elif case == "outside":
        bins[2]["mean_probability"] = 0.35
    elif case == "empty_value":
        bins[7]["observed_rate"] = 0.1
    elif case == "range":
        bins[1]["observed_rate"] = 1.2
    elif case == "length":
        bins = bins[:9]
    elif case == "missing":
        del bins[0]["observed_rate"]
    return bins, None


@pytest.mark.parametrize(
    "case", ["sum", "support", "outside", "empty_value", "range", "length", "missing"]
)
def test_inconsistent_bins_are_not_drawn(tmp_path, case):
    bins, rows = _broken_bins(case)
    report = _write_report(tmp_path / "rapor", bins=bins, rows=rows)
    output = tmp_path / "golge.svg"
    assert _run(report, output) == 1
    assert not output.exists()


def test_report_without_rows_is_not_drawn(tmp_path, capsys):
    report = _write_report(tmp_path / "rapor", bins=_bins({}))
    output = tmp_path / "golge.svg"
    assert _run(report, output) == 1
    assert not output.exists()
    assert "çizilecek satır yok" in capsys.readouterr().err


def test_unverified_chart_is_removed(tmp_path, monkeypatch):
    report = _write_report(tmp_path / "rapor")
    output = tmp_path / "golge.svg"

    def fail(path, source):
        raise ValueError("kova farklı")

    monkeypatch.setattr(reliability, "verify_chart", fail)
    assert _run(report, output) == 1
    assert not output.exists()


def test_command_loads_no_model_database_or_network_layers(tmp_path):
    report = _write_report(tmp_path / "rapor")
    code = r"""
import importlib.abc
import socket
import sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        forbidden = ('numpy', 'sklearn', 'lightgbm', 'psycopg', 'psycopg_pool',
                     'curl_cffi', 'httpx', 'requests', 'filelock',
                     'app.database', 'app.collection', 'app.discovery',
                     'app.market_history', 'app.api', 'app.ui', 'tools')
        if any(fullname == item or fullname.startswith(item + '.')
               for item in forbidden):
            raise AssertionError('Yasak katman: ' + fullname)
def blocked(*args, **kwargs):
    raise AssertionError('Ag baglantisi')
sys.meta_path.insert(0, Guard())
socket.create_connection = blocked
socket.socket.connect = blocked
socket.socket.connect_ex = blocked
from app.ml.__main__ import main
raise SystemExit(main(['reliability-chart', '--report', sys.argv[1],
                       '--output', sys.argv[2]]))
"""
    output = tmp_path / "golge.svg"
    result = subprocess.run(
        [sys.executable, "-c", code, str(report), str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert output.exists()
