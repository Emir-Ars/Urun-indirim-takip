"""API verisini değiştirmeden ekran metinlerini ve grafiklerini hazırlar."""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import altair as alt

from app.api.schemas import HistoryResponse, MarketResponse
from app.contracts import Reason

ISTANBUL = ZoneInfo("Europe/Istanbul")
REASONS: dict[Reason, str] = {
    "no_history": "Tamamlanmış ürün turu bulunmuyor.",
    "incomplete_scope": "Son turda bütün planlanan sayfalar cevaplanmadı.",
    "insufficient_period": "Aynı kapsam dönemi henüz 30 güne ulaşmadı.",
    "no_prices": "Bu dönemde fiyat gözlemi bulunmuyor.",
    "insufficient_transitions": "En az 14 geçerli fiyat geçişi gerekiyor.",
    "insufficient_days": "Geçerli geçişlerde en az 7 farklı İstanbul günü gerekiyor.",
}


def format_money(value: int | None, *, signed: bool = False) -> str:
    if value is None:
        return "—"
    whole, fraction = divmod(abs(value), 100)
    sign = "−" if value < 0 else "+" if signed and value > 0 else ""
    return f"{sign}{format(whole, ',').replace(',', '.')},{fraction:02d} TL"


def format_number(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def format_time(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.astimezone(ISTANBUL).strftime("%d.%m.%Y %H:%M:%S")


def format_day(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def reason_text(reasons: tuple[Reason, ...]) -> str:
    return " ".join(REASONS[reason] for reason in reasons)


def _chart_time(value: datetime) -> str:
    # UTC ekseni tarayıcıdan etkilenmesin; yalnız çizimde İstanbul duvar saati.
    return value.astimezone(ISTANBUL).replace(tzinfo=timezone.utc).isoformat()


def history_rows(points: tuple[HistoryResponse, ...]) -> list[dict]:
    rows = []
    segment = -1
    previous = None
    for index, point in enumerate(points):
        connected = False
        if (
            previous is not None
            and previous.best_price is not None
            and point.best_price is not None
            and not previous.partial
            and not point.partial
            and set(previous.planned_listing_ids) == set(point.planned_listing_ids)
            and previous.best_checked_at is not None
            and point.best_checked_at is not None
        ):
            gap = point.best_checked_at - previous.best_checked_at
            connected = timedelta(0) < gap <= timedelta(hours=18)
        if not connected:
            segment += 1
        rows.append(
            {
                "istanbul_time": _chart_time(point.run_started_at),
                "price_tl": (
                    point.best_price / 100 if point.best_price is not None else None
                ),
                "price_kurus": point.best_price,
                "price_text": format_money(point.best_price),
                "checked_text": format_time(point.best_checked_at),
                "run_text": format_time(point.run_started_at),
                "coverage": f"{point.answered_pages}/{point.planned_pages}",
                "scope": "Kısmi kapsam" if point.partial else "Tam kapsam",
                "sequence": index,
                "segment": segment,
            }
        )
        previous = point
    return rows


def market_rows(points: tuple[MarketResponse, ...]) -> list[dict]:
    rows = []
    segment = -1
    previous = None
    for index, point in enumerate(points):
        if not (
            previous is not None
            and previous.price_kurus is not None
            and point.price_kurus is not None
            and point.day - previous.day == timedelta(days=1)
        ):
            segment += 1
        rows.append(
            {
                "day": point.day.isoformat(),
                "price_tl": (
                    point.price_kurus / 100 if point.price_kurus is not None else None
                ),
                "price_kurus": point.price_kurus,
                "price_text": format_money(point.price_kurus),
                "day_text": format_day(point.day),
                "sequence": index,
                "segment": segment,
            }
        )
        previous = point
    return rows


def price_chart(rows: list[dict], *, market: bool = False) -> alt.LayerChart:
    field = "day" if market else "istanbul_time"
    color = "#0f766e" if market else "#2563eb"
    tooltip = (
        [alt.Tooltip("day_text:N", title="Gün")]
        if market
        else [
            alt.Tooltip("run_text:N", title="Tur başlangıcı (İstanbul)"),
            alt.Tooltip("checked_text:N", title="Fiyat kontrolü (İstanbul)"),
            alt.Tooltip("coverage:N", title="Cevaplanan / planlanan"),
            alt.Tooltip("scope:N", title="Kapsam"),
        ]
    ) + [alt.Tooltip("price_text:N", title="Fiyat")]
    base = alt.Chart(alt.Data(values=rows)).encode(
        x=alt.X(
            f"{field}:T",
            title="Gün" if market else "Tur başlangıcı (İstanbul)",
            scale=alt.Scale(type="utc"),
            axis=alt.Axis(format="%d.%m.%Y" if market else "%d.%m %H:%M"),
        ),
        y=alt.Y("price_tl:Q", title="Fiyat (TL)", scale=alt.Scale(zero=False)),
        tooltip=tooltip,
    )
    line = base.mark_line(color=color, invalid="break-paths-show-domains").encode(
        detail="segment:N", order="sequence:Q"
    )
    dots = base.mark_point(filled=True, size=55, color=color)
    if not market:
        dots = dots.encode(
            shape=alt.Shape(
                "scope:N",
                title="Kapsam",
                scale=alt.Scale(
                    domain=["Tam kapsam", "Kısmi kapsam"], range=["circle", "diamond"]
                ),
            )
        )
    return (line + dots).properties(height=300).interactive()
