from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class PullResult:
    items: list = field(default_factory=list)
    documents: list = field(default_factory=list)
    new_cursor: str = ""
    items_new: int = 0
    items_updated: int = 0
    docs_new: int = 0
    docs_updated: int = 0


class BasePuller(ABC):
    service_id: str

    def __init__(self, service_id: str, credentials: dict, config: dict | None = None):
        self.service_id = service_id
        self.credentials = credentials
        self.config = config or {}

    @abstractmethod
    def test_connection(self) -> bool:
        """Validate credentials and return True if the service is reachable."""
        ...

    @abstractmethod
    def pull(self, cursor: str | None = None, since: str | None = None) -> PullResult:
        """Fetch items from the service. Use cursor/since for incremental pulls."""
        ...

    @abstractmethod
    def normalize(self, raw_item: dict) -> dict:
        """Transform a service-specific item into the unified items schema."""
        ...
