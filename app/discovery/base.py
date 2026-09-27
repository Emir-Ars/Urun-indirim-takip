"""Platform keşiflerinin ortak sınırı ve HTTP bütçesi."""

from abc import ABC, abstractmethod

from app.contracts import DiscoveryIssue
from app.scraper.http import FetchError, PageClient
from app.scraper.parsing import network_type

# Tek bir bozuk kaynak yanıtı bütün keşfi durdurmaz; bu hatalar rapora yazılır.
RECOVERABLE = (FetchError, ValueError, TypeError, KeyError, AttributeError)


def error_code(exc: Exception) -> str:
    """Rapor için hata: FetchError kodu ve mesajı veya beklenmeyen hatanın türü.

    Ör. "blocked: Kaynak HTTP 429 döndürdü (apigw.trendyol.com/...)"; engelin
    türü (429 hız sınırı, 403 erişim reddi) çözümü belirlediği için rapora yazılır.
    """
    code = getattr(exc, "code", None)
    if not code:
        return type(exc).__name__
    return f"{code}: {exc}" if str(exc) else code


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

    def verify_network(self, value, names):
        """Sayfanın yapısal ağ türü hedefle çelişiyorsa reddet.

        Alan boşsa sayfa geçer: satıcılar bu alanı çoğu zaman doldurmuyor ve
        5G sayfaların başlığında zaten "5G" yazıyor (exclude_terms ile dışlanır).
        """
        found = network_type(value)
        if found is not None and found != self.target.network:
            raise FetchError(
                "identity",
                f"Ağ türü hedefle eşleşmiyor ({found}, beklenen "
                f"{self.target.network}): {' | '.join(names)[:160]}",
            )

    @abstractmethod
    def discover(self):
        """Doğrulanmış adaylar ve kapsama raporu döndür."""

    def close(self):
        self.pages.close()
