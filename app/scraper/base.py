"""Canlı platform adaptörlerinin sabit sözleşmesi."""

from abc import ABC, abstractmethod

from app.contracts import PriceObservation, ProductListing, utc_now
from app.scraper.http import FetchError, PageClient
from app.settings import Runtime


class BaseScraper(ABC):
    def __init__(self, hosts: list[str], runtime: Runtime, client=None):
        self.pages = PageClient(hosts, runtime, client)

    def fetch(self, listing: ProductListing) -> PriceObservation:
        try:
            return self.get_product_data(listing)
        except FetchError:
            raise
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise FetchError("parse", f"Teklif doğrulanamadı: {exc}") from exc

    @abstractmethod
    def get_product_data(self, listing: ProductListing) -> PriceObservation:
        """Bağlantıdaki en ucuz geçerli teklifi döndürür."""

    @staticmethod
    def observation(listing: ProductListing, **fields) -> PriceObservation:
        return PriceObservation(
            listing_id=listing.listing_id,
            product_id=listing.product_id,
            platform=listing.platform,
            product_name=listing.product_name,
            product_url=listing.url,
            timestamp=utc_now(),
            **fields,
        )

    def close(self):
        self.pages.close()
