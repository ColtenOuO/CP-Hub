from fastapi import APIRouter

from backend.app.api.v1.endpoints import leetcode

api_router = APIRouter()
api_router.include_router(leetcode.router, prefix="/leetcode", tags=["leetcode"])
