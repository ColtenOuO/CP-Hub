from datetime import datetime

from backend.app.services.leetcode.client import LeetCodeService


def _slug_from_url(url: str) -> str:
    # 從 /problems/<slug>/ 後面正確切出 slug，忽略 /description 等後綴
    # e.g. https://leetcode.com/problems/two-sum/description/ → two-sum
    if "/problems/" in url:
        return url.split("/problems/")[1].split("/")[0]
    return url.rstrip("/").rsplit("/", 1)[-1]


class LeetCodeVerifier:
    def __init__(self, service: LeetCodeService):
        self._service = service

    async def verify(self, handle: str, url: str, after: datetime) -> bool:
        slug = _slug_from_url(url)
        return await self._service.verify_problem_solved(handle, slug, after)
