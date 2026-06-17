from datetime import datetime

from backend.app.services.leetcode.client import LeetCodeService


class LeetCodeVerifier:
    def __init__(self, service: LeetCodeService):
        self._service = service

    async def verify(self, handle: str, url: str, after: datetime) -> bool:
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        return await self._service.verify_problem_solved(handle, slug, after)
