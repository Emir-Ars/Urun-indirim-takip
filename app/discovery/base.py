"""Platform keşiflerinin ortak sınırı ve HTTP bütçesi."""

from abc import ABC, abstractmethod

from app.contracts import DiscoveryIssue
from app.scraper.http import FetchError, PageClient


class BaseDiscovery(ABC):
    platform: str
    hosts: list[str]

    def __init__(self, target, config, runtime, client=None):
        self.target = target
        self.config = config
        self.pages = PageClient(
            self.hosts, runtime, client=client, request_budget=config.max_requests
        )
        self.requests = 0
        self.issues = []
        self.search_pages = 0
        self.product_pages = 0

    def get(self, url, *, headers=None):
        self._count()
        return self.pages.get(url, headers=headers)

    def get_json(self, url, *, headers=None):
        self._count()
        return self.pages.get_json(url, headers=headers)

    def _count(self):
        if self.requests >= self.config.max_requests:
            raise FetchError("limit", "HTTP istek sınırı doldu")
        self.requests += 1

    def issue(self, reason, detail=""):
        self.issues.append(
            DiscoveryIssue(
                platform=self.platform,
                target_key=self.target.key,
                reason=reason,
                detail=str(detail)[:300],
            )
        )

    @abstractmethod
    def discover(self):
        """Doğrulanmış adaylar ve kapsama raporu döndür."""

    def close(self):
        self.pages.close()
