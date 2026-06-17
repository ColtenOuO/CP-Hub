from datetime import datetime
from typing import Protocol


class PlatformVerifier(Protocol):
    async def verify(self, handle: str, url: str, after: datetime) -> bool: ...
