from abc import ABC, abstractmethod

from trackerkit.domain.models import ConnectionDiagnostic


class ConnectionCapability(ABC):
    @abstractmethod
    async def check_connection(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def get_connection_diagnostic(self) -> ConnectionDiagnostic:
        raise NotImplementedError

    async def close(self) -> None:
        return None
