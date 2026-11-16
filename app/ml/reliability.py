"""Kalibrasyon kovalarından güvenilirlik diyagramı (SVG).

Yalnız manifestle doğrulanmış bir saklı test veya gölge değerlendirme raporunu
okur. Yeni ölçüm hesaplamaz; çizilen her değer rapordaki kovanın aynısıdır.
Rapor, model ve resmi kayıtlar değişmez.
"""

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from xml.etree import ElementTree
from xml.sax.saxutils import escape, quoteattr

from app.ml.metrics import METRIC_RULES
from app.ml.reporting import MODEL_TITLES

BIN_COUNT = METRIC_RULES["calibration_bins"]
MIN_SUPPORT = METRIC_RULES["minimum_bin_support"]
MONTHS = (
    "Ocak",
    "Şubat",
    "Mart",
    "Nisan",
    "Mayıs",
    "Haziran",
    "Temmuz",
    "Ağustos",
    "Eylül",
    "Ekim",
    "Kasım",
    "Aralık",
)
SVG_NS = "http://www.w3.org/2000/svg"

# Yerleşim (piksel). Grafik alanı kare olduğu için köşegen 45 derecedir.
WIDTH, HEIGHT = 640, 826
PLOT_LEFT, PLOT_TOP, PLOT_SIZE = 80, 120, 460
BAR_TOP, BAR_HEIGHT = 640, 60
POINT = "#1f5fa8"
BAR = "#9db9dc"
GRID = "#e3e6ea"
TEXT = "#1d2329"
MUTED = "#5b6670"


@dataclass(frozen=True)
class ReliabilitySource:
    kind: str
    choice: str
    bins: tuple
    rows: int
    first_anchor: str | None
    last_anchor: str | None
    last_closed_day: str | None
    final_date: bool
    report_sha256: str
    folder_name: str


def load_source(report_dir: Path) -> ReliabilitySource:
    manifest = json.loads((report_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "complete":
        raise ValueError("Rapor tamamlanmamış: manifest durumu 'complete' değil")
    raw = (report_dir / "report.json").read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    # Grafik yalnız manifestin kaydettiği rapordan çizilir; elle değişmiş
    # bir rapor sessizce görsele dönüşmesin.
    if (manifest.get("files") or {}).get("report.json") != digest:
        raise ValueError("report.json manifestteki SHA-256 ile eşleşmiyor")
    report = json.loads(raw.decode("utf-8"))
    try:
        if manifest.get("kind") == "shadow_evaluation":
            choice = report["input"]["choice"]
            score = report["scores"]["main"][choice]
            gate = report["gate"]
            period = (gate["first_anchor"], gate["last_anchor"])
            closed = report["input"]["last_closed_day"]
            final_date = report["final_date_matches"] is True
            kind = "shadow_evaluation"
        elif manifest.get("test_opened") is True and "reserved_test" in report:
            choice = report["choice"]
            score = report["scores"][choice]
            test = report["reserved_test"]
            period = (test["first_anchor"], test["last_anchor"])
            closed, final_date, kind = None, False, "final_test"
        else:
            raise ValueError(
                "Desteklenmeyen rapor: yalnız saklı test veya gölge "
                "değerlendirme raporu çizilir"
            )
        bins = _validated_bins(score["calibration"], score["rows"])
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Rapor beklenen alanları taşımıyor: {exc!r}") from exc
    if choice not in MODEL_TITLES:
        raise ValueError(f"Tanınmayan model: {choice}")
    return ReliabilitySource(
        kind=kind,
        choice=choice,
        bins=bins,
        rows=score["rows"],
        first_anchor=period[0],
        last_anchor=period[1],
        last_closed_day=closed,
        final_date=final_date,
        report_sha256=digest,
        folder_name=report_dir.resolve().name,
    )


def _validated_bins(bins, rows) -> tuple:
    if not isinstance(bins, list) or len(bins) != BIN_COUNT:
        raise ValueError(f"Kalibrasyon kovaları {BIN_COUNT} kova değil")
    if type(rows) is not int or rows <= 0:
        raise ValueError("Raporda çizilecek satır yok")
    clean = []
    for index, item in enumerate(bins):
        lower, upper = index / BIN_COUNT, (index + 1) / BIN_COUNT
        if not (
            math.isclose(item["lower"], lower) and math.isclose(item["upper"], upper)
        ):
            raise ValueError(f"{index + 1}. kovanın sınırları beklenen değil")
        count, low_support = item["count"], item["low_support"]
        mean, observed = item["mean_probability"], item["observed_rate"]
        if type(count) is not int or count < 0 or type(low_support) is not bool:
            raise ValueError(
                f"{index + 1}. kovanın sayısı veya destek bilgisi geçersiz"
            )
        if low_support != (count < MIN_SUPPORT):
            raise ValueError(f"{index + 1}. kovanın destek işareti sayısıyla çelişiyor")
        if count == 0:
            if mean is not None or observed is not None:
                raise ValueError(f"{index + 1}. kova boş ama değer taşıyor")
        else:
            for value in (mean, observed):
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError(f"{index + 1}. kovanın değeri sayı değil")
                if not 0 <= value <= 1:
                    raise ValueError(f"{index + 1}. kovanın değeri 0–1 dışında")
            # Ortalama olasılık kendi kovasının içinde olmalıdır.
            if not lower - 1e-12 <= mean <= upper + 1e-12:
                raise ValueError(f"{index + 1}. kovanın ortalaması kova dışında")
        clean.append(
            dict(
                index=index,
                lower=lower,
                upper=upper,
                count=count,
                mean_probability=mean,
                observed_rate=observed,
                low_support=low_support,
            )
        )
    if sum(item["count"] for item in clean) != rows:
        raise ValueError("Kova sayılarının toplamı rapordaki satır sayısına eşit değil")
    return tuple(clean)


def render_svg(source: ReliabilitySource) -> str:
    def x(value):
        return PLOT_LEFT + value * PLOT_SIZE

    def y(value):
        return PLOT_TOP + (1 - value) * PLOT_SIZE

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="{SVG_NS}" width="{WIDTH}" height="{HEIGHT}" '
            f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" '
            'font-family="Segoe UI, Arial, sans-serif">'
        ),
        f"<title>{escape(_title(source))}</title>",
        f"<desc>{escape(_description(source))}</desc>",
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#ffffff"/>',
        _text(WIDTH / 2, 34, "Güvenilirlik diyagramı", 20, TEXT, "middle", "bold"),
    ]
    for offset, line in enumerate(_header_lines(source)):
        parts.append(_text(WIDTH / 2, 58 + 18 * offset, line, 13, MUTED, "middle"))
    for step in range(11):
        value = step / 10
        parts.append(_line(x(value), y(0), x(value), y(1), GRID))
        parts.append(_line(x(0), y(value), x(1), y(value), GRID))
        parts.append(
            _text(x(value), y(0) + 18, _percent(value, 0), 11, MUTED, "middle")
        )
        parts.append(
            _text(x(0) - 8, y(value) + 4, _percent(value, 0), 11, MUTED, "end")
        )
    parts.append(
        f'<rect x="{x(0):.2f}" y="{y(1):.2f}" width="{PLOT_SIZE}" '
        f'height="{PLOT_SIZE}" fill="none" stroke="{MUTED}" stroke-width="1"/>'
    )
    parts.append(
        _line(
            x(0), y(0), x(1), y(1), MUTED, 'stroke-dasharray="6 5" stroke-width="1.5"'
        )
    )
    parts.append(
        _text(
            x(0) + PLOT_SIZE / 2,
            y(0) + 40,
            "Modelin verdiği olasılık (kovadaki ortalama)",
            13,
            TEXT,
            "middle",
        )
    )
    middle = y(0.5)
    parts.append(
        f'<text x="26" y="{middle:.2f}" font-size="13" fill="{TEXT}" '
        f'text-anchor="middle" transform="rotate(-90 26 {middle:.2f})">'
        "Gerçekleşen düşüş oranı</text>"
    )
    filled = [item for item in source.bins if item["count"]]
    supported = [item for item in filled if not item["low_support"]]
    if len(supported) > 1:
        points = " ".join(
            f"{x(item['mean_probability']):.2f},{y(item['observed_rate']):.2f}"
            for item in supported
        )
        parts.append(
            f'<polyline points="{points}" fill="none" stroke="{POINT}" '
            'stroke-width="1.5" opacity="0.6"/>'
        )
    for item in filled:
        cx, cy = x(item["mean_probability"]), y(item["observed_rate"])
        fill = "#ffffff" if item["low_support"] else POINT
        parts.append(
            f'<circle class="bin" cx="{cx:.2f}" cy="{cy:.2f}" r="6" fill="{fill}" '
            f'stroke="{POINT}" stroke-width="2" '
            f'data-bin="{item["index"]}" data-count="{item["count"]}" '
            f'data-mean={quoteattr(repr(item["mean_probability"]))} '
            f'data-observed={quoteattr(repr(item["observed_rate"]))} '
            f'data-low-support="{str(item["low_support"]).lower()}"/>'
        )
    # Satır sayıları noktaların yanına değil çubuklara yazılır: yakın kovaların
    # etiketleri grafik alanında üst üste binmesin.
    largest = max(item["count"] for item in filled)
    width = PLOT_SIZE / BIN_COUNT - 4
    for item in filled:
        height = BAR_HEIGHT * item["count"] / largest
        left = x(item["lower"]) + 2
        top = BAR_TOP + BAR_HEIGHT - height
        parts.append(
            f'<rect class="bar" x="{left:.2f}" y="{top:.2f}" '
            f'width="{width:.2f}" height="{height:.2f}" '
            f'fill="{BAR}" data-bin="{item["index"]}" data-count="{item["count"]}"/>'
        )
        parts.append(
            _text(left + width / 2, top - 4, _number(item["count"]), 10, TEXT, "middle")
        )
    parts.append(_line(x(0), BAR_TOP + BAR_HEIGHT, x(1), BAR_TOP + BAR_HEIGHT, MUTED))
    parts.append(
        _text(
            x(0) + PLOT_SIZE / 2,
            BAR_TOP + BAR_HEIGHT + 18,
            "Kovadaki satır sayısı",
            12,
            MUTED,
            "middle",
        )
    )
    legend = BAR_TOP + BAR_HEIGHT + 46
    parts.extend(
        [
            _legend_circle(x(0) + 6, legend - 4, POINT),
            _text(x(0) + 18, legend, f"En az {MIN_SUPPORT} satırlı kova", 12, TEXT),
            _legend_circle(x(0) + 196, legend - 4, "#ffffff"),
            _text(
                x(0) + 208,
                legend,
                f"{MIN_SUPPORT}'den az satırlı kova (düşük destek)",
                12,
                TEXT,
            ),
            _line(
                x(0),
                legend + 18,
                x(0) + 22,
                legend + 18,
                MUTED,
                'stroke-dasharray="6 5" stroke-width="1.5"',
            ),
            _text(x(0) + 30, legend + 22, "Köşegen: mükemmel kalibrasyon", 12, TEXT),
            _text(
                x(0),
                legend + 42,
                "Nokta köşegenin üstündeyse model düşüş olasılığını düşük, "
                "altındaysa yüksek tahmin etmiştir.",
                11,
                MUTED,
            ),
            _text(
                WIDTH / 2,
                HEIGHT - 14,
                f"Kaynak: {source.folder_name}/report.json · SHA-256 "
                f"{source.report_sha256[:16]}…",
                10,
                MUTED,
                "middle",
            ),
            "</svg>",
        ]
    )
    return "\n".join(parts) + "\n"


def write_chart(path: Path, text: str) -> str:
    data = text.encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    # "x" kipi var olan dosyanın üzerine yazmayı işletim sistemi düzeyinde engeller.
    with path.open("xb") as handle:
        try:
            handle.write(data)
        except BaseException:
            handle.close()
            path.unlink(missing_ok=True)
            raise
    if path.read_bytes() != data:
        raise OSError("Yazılan grafik yeniden okununca üretilen metinden farklı")
    return hashlib.sha256(data).hexdigest()


def verify_chart(path: Path, source: ReliabilitySource) -> None:
    root = ElementTree.fromstring(path.read_bytes())
    circles = root.findall(f".//{{{SVG_NS}}}circle[@class='bin']")
    bars = root.findall(f".//{{{SVG_NS}}}rect[@class='bar']")
    filled = [item for item in source.bins if item["count"]]
    if len(circles) != len(filled) or len(bars) != len(filled):
        raise ValueError("Grafikteki nokta/çubuk sayısı dolu kova sayısına eşit değil")
    for circle, bar, item in zip(circles, bars, filled):
        drawn = (
            int(circle.get("data-bin")),
            int(circle.get("data-count")),
            float(circle.get("data-mean")),
            float(circle.get("data-observed")),
            circle.get("data-low-support") == "true",
            int(bar.get("data-bin")),
            int(bar.get("data-count")),
        )
        expected = (
            item["index"],
            item["count"],
            item["mean_probability"],
            item["observed_rate"],
            item["low_support"],
            item["index"],
            item["count"],
        )
        if drawn != expected:
            raise ValueError(f"{item['index'] + 1}. kova grafikte rapordan farklı")


def _title(source):
    return f"Güvenilirlik diyagramı — {MODEL_TITLES[source.choice]}"


def _description(source):
    filled = [item for item in source.bins if item["count"]]
    pieces = [
        f"{_percent(item['lower'], 0)}–{_percent(item['upper'], 0)} kovası: "
        f"{item['count']} satır, ortalama olasılık "
        f"{_percent(item['mean_probability'], 1)}, gerçekleşen "
        f"{_percent(item['observed_rate'], 1)}"
        for item in filled
    ]
    return " · ".join(_header_lines(source)) + ". " + "; ".join(pieces) + "."


def _header_lines(source):
    model = f"Dondurulan model: {MODEL_TITLES[source.choice]}"
    period = _period(source.first_anchor, source.last_anchor)
    if source.kind == "final_test":
        return (
            f"Saklı test (Cimri) · {_number(source.rows)} satır",
            period,
            f"{model} · saklı test bir kez açıldı",
        )
    stage = (
        "5 Ocak 2027 kesin değerlendirme görüntüsü"
        if source.final_date
        else "ara rapor, yalnız bilgi"
    )
    rows = _number(source.rows)
    return (
        f"Gölge değerlendirme · asıl sonuç, kendi verimiz · {rows} satır",
        f"{period} · son kapanmış gün {_date(source.last_closed_day)}",
        f"{model} · {stage}",
    )


def _period(first, last):
    if not first or not last:
        return "Başlangıç aralığı yok"
    start, end = date.fromisoformat(first), date.fromisoformat(last)
    left = _date(first) if start.year != end.year else _date(first).rsplit(" ", 1)[0]
    return f"Başlangıçlar {left} – {_date(last)}"


def _date(text):
    if not text:
        return "—"
    day = date.fromisoformat(text)
    return f"{day.day} {MONTHS[day.month - 1]} {day.year}"


def _percent(value, digits):
    return f"%{100 * value:.{digits}f}".replace(".", ",")


def _number(value):
    return f"{value:,}".replace(",", ".")


def _legend_circle(cx, cy, fill):
    return (
        f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="6" fill="{fill}" '
        f'stroke="{POINT}" stroke-width="2"/>'
    )


def _line(x1, y1, x2, y2, color, extra='stroke-width="1"'):
    return (
        f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
        f'stroke="{color}" {extra}/>'
    )


def _text(x, y, content, size, color, anchor="start", weight="normal"):
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" fill="{color}" '
        f'text-anchor="{anchor}" font-weight="{weight}">{escape(content)}</text>'
    )
