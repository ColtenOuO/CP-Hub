from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from backend.app.services.leetcode.client import LeetCodeService


@lru_cache
def get_leetcode_service() -> LeetCodeService:
    """Returns a shared LeetCodeService; it keeps no per-request state and opens its own HTTP client per call."""
    return LeetCodeService()


LeetCodeServiceDep = Annotated[LeetCodeService, Depends(get_leetcode_service)]
