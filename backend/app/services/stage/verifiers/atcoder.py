from datetime import datetime

import httpx


class AtCoderVerifier:
    _api = "https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions"

    async def verify(self, handle: str, url: str, after: datetime) -> bool:
        problem_id = url.rstrip("/").rsplit("/", 1)[-1]
        after_ts = int(after.timestamp())

        async with httpx.AsyncClient() as client:
            try:
                r = await client.get(
                    self._api,
                    params={"user": handle, "epoch_second": after_ts},
                    timeout=10.0,
                )
                submissions = r.json()
            except httpx.RequestError as exc:
                raise RuntimeError(f"Error verifying AtCoder submission: {exc}")

        return any(s.get("result") == "AC" and s.get("problem_id") == problem_id for s in submissions)
