"""Base Connector Abstraction for NEXUS External Integrations."""

from abc import ABC, abstractmethod
from typing import Any

from packages.shared.nexus_shared.tools.base import BaseTool


class BaseConnector(ABC):
    """Abstract base class for all NEXUS external provider connectors."""

    provider: str

    @abstractmethod
    async def connect(
        self,
        user_id: str,
        credentials: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Authenticate or initialize integration with credentials for given user."""
        ...

    @abstractmethod
    async def disconnect(self, user_id: str) -> bool:
        """Revoke or clean up integration credentials for given user."""
        ...

    @abstractmethod
    async def health_check(self, user_id: str) -> dict[str, Any]:
        """Verify provider availability and credential validity for given user."""
        ...

    @abstractmethod
    def register_tools(self) -> list[BaseTool]:
        """Return the list of executable tools exposed by this connector."""
        ...
