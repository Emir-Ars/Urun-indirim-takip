"""Piyasa geçmişini sınırlı isteklerle araştırır; veritabanına yazmaz."""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

from app.console import utf8_output
from app.contracts import Catalog
from app.market_history.cimri import (
    CIMRI_API_URL,
    cimri_history,
    cimri_page_data,
)
from app.scrape_lock import ScrapeBusy, scrape_lock
from app.scraper.http import FetchError, PageClient
from app.scraper.parsing import verify_identity
from app.settings import Settings

SAMPLE_KEYS = (
    "apple_iphone_16_128gb",
    "samsung_galaxy_s24_256gb",
    "xiaomi_14t_pro_256gb",
)
SOURCE_HOSTS = {
    "akakce": ["www.akakce.com", "akakce.com"],
    "cimri": ["www.cimri.com", "cimri.com"],
}
DATE_FORMATS = ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d")
PRICE_PATTERN = re.compile(r"\d[\d.,\s]*\s*(?:TL|₺)\b|₺\s*\d", re.I)


def candidate_date(value: str) -> str | None:
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), date_format).date().isoformat()
        except ValueError:
            continue
    return None


def summarize_html(html: str, product) -> dict:
    """Görünen ipuçlarını özetler; aday satırları geçmiş diye onaylamaz."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    headings = [item.get_text(" ", strip=True) for item in soup.find_all("h1")]
    names = headings + ([title] if title else [])
    try:
        verify_identity(names, product.model, product.storage_gb)
        identity = {"status": "matched", "detail": None}
    except FetchError as exc:
        identity = {"status": "unverified", "detail": str(exc)}

    tables = []
    for table in soup.find_all("table"):
        headers = " ".join(
            cell.get_text(" ", strip=True) for cell in table.find_all("th")
        )
        if "tarih" not in headers.casefold() or "fiyat" not in headers.casefold():
            continue
        rows = []
        for row in table.find_all("tr"):
            cells = [cell.get_text(" ", strip=True) for cell in row.find_all("td")]
            if len(cells) < 2:
                continue
            day = candidate_date(cells[0])
            if day and PRICE_PATTERN.search(cells[1]):
                rows.append({"day": day, "price_text": cells[1][:80]})
        days = sorted({row["day"] for row in rows})
        tables.append(
            {
                "header": headers[:160],
                "candidate_rows": len(rows),
                "unique_days": len(days),
                "oldest_day": days[0] if days else None,
                "newest_day": days[-1] if days else None,
                "examples": rows[:3],
            }
        )

    scripts = soup.find_all("script")
    visible_text = soup.get_text(" ", strip=True).casefold()
    return {
        "title": title[:200],
        "headings": headings[:3],
        "identity": identity,
        "table_count": len(soup.find_all("table")),
        "candidate_tables": tables,
        "script_count": len(scripts),
        "script_ids": [tag.get("id") for tag in scripts if tag.get("id")][:15],
        "has_history_label": "fiyat geçmiş" in visible_text,
        "has_chart_element": bool(soup.find(["canvas", "svg"])),
        "interpretation": "Aday satırlar manuel doğrulama gerektirir.",
    }


def probe(source: str, url: str, product, runtime, client_class=PageClient) -> dict:
    report = {
        "source": source,
        "product_key": product.product_key,
        "product_name": product.name,
        "url": url,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "request_count": 0,
        "result": "error",
    }
    client = client_class(SOURCE_HOSTS[source], runtime, request_budget=4)
    try:
        html = client.get(url)
        report["page_summary"] = summarize_html(html, product)
        if source == "cimri":
            identity = report["page_summary"]["identity"]
            if identity["status"] != "matched":
                raise FetchError("identity", identity["detail"])
            product_id, table_rows = cimri_page_data(html)
            response = client.post_json(
                CIMRI_API_URL,
                {
                    "queryName": "priceHistoryV2Query",
                    "variables": {"productId": product_id},
                    "platform": "CIMRI_DESKTOP_V2",
                },
                headers={"Referer": url},
            )
            report["history"] = cimri_history(response, product_id, table_rows)
        report["result"] = "inspection_needed"
    except FetchError as exc:
        report["error"] = {"code": exc.code, "detail": str(exc)}
    finally:
        report["request_count"] = client.request_count
        client.close()
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=SOURCE_HOSTS)
    parser.add_argument("product_key", choices=SAMPLE_KEYS)
    parser.add_argument("url", help="Tarayıcıda bulunan ürün geçmişi HTTPS adresi")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/market_history_probe"),
        help="Yerel JSON rapor klasörü (Git dışında)",
    )
    args = parser.parse_args(argv)
    utf8_output()
    settings = Settings()
    catalog = Catalog.model_validate_json(
        settings.catalog_path.read_text(encoding="utf-8-sig")
    )
    product = next(
        (item for item in catalog.products if item.product_key == args.product_key),
        None,
    )
    if product is None or not product.active:
        print("Örnek ürün etkin katalogda bulunamadı.", file=sys.stderr)
        return 1
    try:
        with scrape_lock(settings.lock_path):
            report = probe(args.source, args.url, product, settings.runtime())
    except ScrapeBusy as exc:
        print(f"Başlatılmadı: {exc}", file=sys.stderr)
        return 3
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / f"{args.source}_{args.product_key}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Rapor: {path}")
    print(f"Durum: {report['result']}; HTTP isteği: {report['request_count']}")
    if "history" in report:
        summary = report["history"]["summary"]
        print(
            f"Geçmiş: {summary['point_count']} nokta, "
            f"{summary['oldest_day']}–{summary['newest_day']}; "
            f"tablo eşleşmesi: {summary['table_compared_rows']} satır"
        )
    if "error" in report:
        print(f"Hata: {report['error']['code']}: {report['error']['detail']}")
    return 0 if report["result"] == "inspection_needed" else 2


if __name__ == "__main__":
    sys.exit(main())
