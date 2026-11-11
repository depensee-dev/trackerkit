from abc import ABC, abstractmethod

from trackerkit.domain.models import Comment, CreateCommentInput


class CommentCapability(ABC):
    @abstractmethod
    async def list_comments(self, task_id: str) -> list[Comment]:
        raise NotImplementedError

    @abstractmethod
    async def create_comment(self, payload: CreateCommentInput) -> Comment:
        raise NotImplementedError

