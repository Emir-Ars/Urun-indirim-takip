"""Platform keşiflerinin ortak sınırı ve HTTP bütçesi."""

from abc import ABC, abstractmethod

from app.contracts import DiscoveryIssue
from app.scraper.http import FetchError, PageClient

# Tek bir bozuk kaynak yanıtı bütün keşfi durdurmaz; bu hatalar rapora yazılır.
RECOVERABLE = (FetchError, ValueError, TypeError, KeyError, AttributeError)


def error_code(exc: Exception) -> str:
    """Rapor için hata kodu: FetchError kodu veya beklenmeyen hatanın türü."""
    return getattr(exc, "code", None) or type(exc).__name__


class BaseDiscovery(ABC):
    platform: str
    hosts: list[str]

    def __init__(self, target, config, runtime):
        self.target = target
        self.config = config
        self.pages = PageClient(self.hosts, runtime, request_budget=config.max_requests)
        self.issues = []
        self.trace = []
        self.search_pages = 0
        self.product_pages = 0

    # İstek bütçesini PageClient uygular; yeniden denemeler ve yönlendirmeler
    # dahil gerçek HTTP denemelerini sayar (self.pages.request_count).
    def get(self, url, *, headers=None):
        return self.pages.get(url, headers=headers)

    def get_json(self, url, *, headers=None):
        return self.pages.get_json(url, headers=headers)

    def issue(self, reason, detail=""):
        self.issues.append(
            DiscoveryIssue(
                platform=self.platform,
                target_key=self.target.key,
                reason=reason,
                detail=str(detail)[:300],
            )
        )

    def note(self, kind, **fields):
        """Sessiz kararların tanılama izi; rapora ve kataloğa yazılmaz."""
        self.trace.append({"kind": kind, **fields})

    @abstractmethod
    def discover(self):
        """Doğrulanmış adaylar ve kapsama raporu döndür."""

    def close(self):
        self.pages.close()
