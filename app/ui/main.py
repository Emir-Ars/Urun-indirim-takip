"""Yerel API'nin doğrulanmış verilerini gösteren Streamlit ekranı."""

from collections.abc import Callable

import streamlit as st

from app.api.schemas import ListingResponse, ProductResponse, StatusResponse
from app.ui.api_client import ApiClient, ApiClientError
from app.ui.presentation import (
    format_day,
    format_money,
    format_number,
    format_time,
    history_rows,
    market_rows,
    price_chart,
    reason_text,
)

DAYS = (7, 30, 90, 366)


def _run_status(status: StatusResponse) -> None:
    with st.expander("Sistem turu · seçilen telefonun sonucundan ayrı"):
        if status.running is None:
            st.text("Kayıtlı çalışan tur yok.")
        else:
            st.text(
                f"Kayıtlı çalışan tur: {status.running.run_id} · "
                f"başlangıç: {format_time(status.running.started_at)}"
            )
        if status.completed is None:
            st.text("Tamamlanmış global tur yok.")
        else:
            st.text(
                f"Son tamamlanmış global tur: {status.completed.run_id} · "
                f"kapanış: {format_time(status.completed.finished_at)}"
            )


def _offer_details(offer: ListingResponse) -> None:
    st.text(f"{offer.platform_name} · Satıcı: {offer.seller_name or 'Bilinmiyor'}")
    rating = "Bilinmiyor"
    if offer.seller_rating is not None:
        rating = format_number(offer.seller_rating)
        if offer.seller_rating_scale is not None:
            rating += f" / {format_number(offer.seller_rating_scale)}"
    st.text(f"Satıcı puanı: {rating} · Renk: {offer.color}")
    st.text(f"Stok: {offer.stock_status or 'Bilinmiyor'}")
    st.caption(f"Fiyat kontrolü: {format_time(offer.checked_at)} · İstanbul")


def _current(snapshot: ProductResponse) -> None:
    current = snapshot.current
    with st.container(border=True):
        st.subheader("🏷️ Güncel sonuç")
        if snapshot.state == "offer":
            offer = snapshot.best_offer
            delta = None
            if current.comparable_with_previous and current.previous_best_price:
                delta = format_money(
                    offer.current_price - current.previous_best_price, signed=True
                )
            st.metric(
                "Takip edilen en ucuz teklif",
                format_money(offer.current_price),
                delta=delta,
                delta_color="inverse",
            )
            if delta is not None:
                st.caption("Değişim: önceki karşılaştırılabilir ürün turuna göre.")
            else:
                st.caption("Önceki turla fiyat karşılaştırması bulunmuyor.")
            _offer_details(offer)
            if offer.original_price is not None:
                st.caption(
                    "Satıcının belirttiği eski fiyat: "
                    f"{format_money(offer.original_price)}"
                )
            if offer.stock_status == "Kritik Stok":
                st.warning("Kaynak kritik stok bildiriyor.")
            if snapshot.is_stale:
                st.warning("Bu teklifin kontrolü en az 18 saat önce yapıldı.")
            st.link_button("Ürün sayfasını aç", offer.url)
        elif snapshot.state == "sold_out":
            st.info("Takip edilen bütün sayfalarda stok yok.")
        elif snapshot.state == "unverified":
            st.warning("Son tamamlanmış turda fiyat doğrulanamadı.")
        else:
            st.info("Bu telefon için tamamlanmış toplama turu bulunmuyor.")
        if current is not None:
            st.caption(
                f"Ürün turu: {current.run_id} · Son kontrol: "
                f"{format_time(current.last_checked_at)} · İstanbul"
            )
            st.text(
                f"Cevaplanan (fiyat/stok): {current.answered_pages}/"
                f"{current.planned_pages} · Hata: {current.error_pages} · "
                f"Kontrol edilmeyen: {current.unchecked_pages}"
            )
            if current.partial:
                st.warning("Kısmi kapsam: bütün planlanan sayfalar cevaplanmadı.")
        previous = snapshot.last_successful_offer
        if previous is not None and (
            snapshot.best_offer is None or previous != snapshot.best_offer
        ):
            with st.expander("Son başarılı teklif · güncel fiyatın yerine kullanılmaz"):
                st.metric("Son başarılı fiyat", format_money(previous.current_price))
                _offer_details(previous)


def _statistics(snapshot: ProductResponse) -> None:
    st.subheader("📊 Fiyat istatistikleri")
    statistics = snapshot.statistics
    indicators = (
        ("30 günlük gözlenen dip", statistics.low_30d, False),
        ("Mevcut kapsam döneminin zirvesi", statistics.high_in_scope, False),
        ("Fiyat değişkenliği", statistics.volatility_30d, True),
    )
    for column, (label, indicator, volatility) in zip(st.columns(3), indicators):
        with column:
            value = (
                format_number(indicator.value)
                if volatility
                else format_money(indicator.value)
            )
            st.metric(label, value, border=True)
            if indicator.reasons:
                st.caption(reason_text(indicator.reasons))
            st.caption(f"Fiyat gözlemi: {indicator.observations}")
            if volatility:
                st.caption(
                    f"Geçerli geçiş: {indicator.transitions} · Gün: {indicator.days}"
                )
    with st.expander("İstatistik dönemleri ve anlamı"):
        st.text(f"Aynı kapsam dönemindeki tur sayısı: {statistics.scope_runs}")
        for label, indicator, volatility in indicators:
            st.text(
                f"{label}: {format_time(indicator.period_started_at)} — "
                f"{format_time(indicator.period_ended_at)} (İstanbul)"
            )
        st.caption(
            "Değişkenlik: log fiyat değişimlerinin örnek standart sapması × 100; "
            "yıllıklaştırılmaz. Grafik aralığı bu istatistikleri değiştirmez."
        )


def _checks(snapshot: ProductResponse) -> None:
    with st.expander("Planlanan bütün sayfaların sonuçları"):
        if not snapshot.checks:
            st.info("Kayıtlı sayfa sonucu bulunmuyor.")
            return
        outcomes = {"offer": "Teklif", "sold_out": "Tükendi", "error": "Okunamadı"}
        st.dataframe(
            [
                {
                    "Platform": check.platform_name,
                    "Sayfa": check.listing_id,
                    "Renk": check.color,
                    "Sonuç": outcomes.get(check.outcome, "Kontrol edilmedi"),
                    "Fiyat": format_money(check.current_price),
                    "Satıcı": check.seller_name or "—",
                    "Stok": check.stock_status or "—",
                    "Kontrol (İstanbul)": format_time(check.checked_at),
                    "Hata kodu": check.error_code or "—",
                    "Sayfa etkin": "Evet" if check.listing_active else "Hayır",
                    "Platform etkin": "Evet" if check.platform_active else "Hayır",
                    "Adres": check.url,
                }
                for check in snapshot.checks
            ],
            hide_index=True,
            width="stretch",
            column_config={"Adres": st.column_config.LinkColumn("Adres")},
        )
        st.caption(
            "Fiyat, satıcı ve stok tur sonucudur. Adres, renk ve etkinlik "
            "mevcut katalog bilgisidir; geçmiş katalog değeri değildir."
        )


def _histories(snapshot: ProductResponse, history_days: int, cimri_days: int) -> None:
    st.subheader("📈 Kendi fiyat geçmişimiz")
    st.caption(
        f"Son kayıtlı ürün turundan geriye {history_days} gün. "
        "Kısmi kapsam elmasla gösterilir; eksik fiyat ve uzun boşluklar bağlanmaz."
    )
    if not snapshot.history:
        st.info("Kendi fiyat geçmişimiz bulunmuyor.")
    elif all(point.best_price is None for point in snapshot.history):
        st.info("Seçilen aralıkta kayıtlı turlar var; fiyat gözlemi bulunmuyor.")
    else:
        st.altair_chart(
            price_chart(history_rows(snapshot.history)),
            width="stretch",
            key="own_history_chart",
        )
    st.subheader("📅 Cimri geçmişi · ayrı kaynak")
    if not snapshot.cimri_history:
        st.info("Cimri geçmişi bulunmuyor")
        return
    points = snapshot.cimri_history
    st.caption(
        f"Son kayıtlı günden geriye {cimri_days} gün · "
        f"{format_day(points[0].day)} — {format_day(points[-1].day)} · "
        f"Eksik fiyat: {sum(point.price_kurus is None for point in points)}"
    )
    if all(point.price_kurus is None for point in points):
        st.info("Seçilen Cimri aralığında fiyatlar eksik.")
    else:
        st.altair_chart(
            price_chart(market_rows(points), market=True),
            width="stretch",
            key="cimri_history_chart",
        )
    st.caption(
        "Cimri'nin bir defalık kaydedilmiş geçmişidir; kendi toplama serimizle "
        "birleştirilmez. Tekrarlanan fiyatlar ayrı ölçüm yapıldığını kanıtlamaz."
    )


def render_app(client_factory: Callable[[], ApiClient] = ApiClient) -> None:
    st.set_page_config(page_title="Telefon Fiyat Takibi", page_icon="📱", layout="wide")
    st.title("📱 Telefon Fiyat Takibi")
    st.caption("Kayıtlı sonuçlar · Oturum açıkken 30 saniyede bir yenilenir")

    @st.fragment(run_every=30)
    def live_panel():
        controls_rendered = False
        try:
            with client_factory() as client:
                products = client.list_products()
                status = client.get_status()
                if not products:
                    st.info("Etkin telefon bulunmuyor.")
                    _run_status(status)
                    st.button("Yenile", key="refresh")
                    return
                names = {product.product_key: product.name for product in products}
                previous = st.session_state.get("selected_product")
                if st.session_state.get("_product") not in names:
                    st.session_state["_product"] = (
                        previous if previous in names else products[0].product_key
                    )
                if previous is not None and previous not in names:
                    st.info(
                        "Seçilen telefon artık etkin listede değil; "
                        "ilk telefon seçildi."
                    )
                selector, refresh = st.columns([5, 1], vertical_alignment="bottom")
                with selector:
                    selected = st.selectbox(
                        "Telefon",
                        tuple(names),
                        format_func=names.__getitem__,
                        key="_product",
                    )
                with refresh:
                    st.button("Yenile", key="refresh", width="stretch", type="primary")
                controls_rendered = True
                st.session_state["selected_product"] = selected
                ranges = []
                for column, label, key, default in zip(
                    st.columns(2),
                    ("Kendi grafiğimiz · gün", "Cimri grafiği · gün"),
                    ("history_days", "cimri_days"),
                    (30, 366),
                ):
                    widget = f"_{key}"
                    if widget not in st.session_state:
                        st.session_state[widget] = st.session_state.get(key, default)
                    with column:
                        value = st.selectbox(label, DAYS, key=widget)
                    st.session_state[key] = value
                    ranges.append(value)
                snapshot = client.get_product(selected, *ranges)
            _run_status(status)
            _current(snapshot)
            _statistics(snapshot)
            _histories(snapshot, *ranges)
            _checks(snapshot)
            st.caption(f"API cevabı: {format_time(snapshot.generated_at)} · İstanbul")
        except ApiClientError as error:
            st.error(error.message)
            st.caption("Yenilemede yeniden denenecek; önceki fiyatlar gösterilmiyor.")
            if not controls_rendered:
                st.button("Yenile", key="refresh")

    live_panel()


if __name__ == "__main__":
    render_app()
