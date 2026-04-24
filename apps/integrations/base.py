from abc import ABC, abstractmethod


class ChannelHandler(ABC):
    """Abstract base for all messaging channel handlers."""

    @abstractmethod
    async def handle_incoming_update(self, update: dict, salon) -> None:
        """Parse incoming webhook payload and dispatch to Celery."""
        ...

    @abstractmethod
    async def send_message(self, salon, external_chat_id: str, text: str) -> None:
        """Send a text message back to the user on this channel."""
        ...
