from abc import ABC, abstractmethod

from trackerkit.domain.models import User


class UserCapability(ABC):
    @abstractmethod
    async def list_users(self) -> list[User]:
        raise NotImplementedError

