from datetime import datetime

import httpx


def _parse_url(url: str) -> tuple[str, str]:
    # https://codeforces.com/problemset/problem/1829/F
    # https://codeforces.com/contest/1829/problem/F
    parts = url.rstrip("/").split("/")
    return parts[-2], parts[-1].upper()


class CodeforcesVerifier:
    async def verify(self, handle: str, url: str, after: datetime) -> bool:
        contest_id, problem_index = _parse_url(url)
        after_ts = int(after.timestamp())

        async with httpx.AsyncClient() as client:
            try:
                r = await client.get(
                    "https://codeforces.com/api/user.status",
                    params={"handle": handle, "from": 1, "count": 20},
                    timeout=10.0,
                )
                data = r.json()
            except httpx.RequestError as exc:
                raise RuntimeError(f"Error verifying Codeforces submission: {exc}")

        if data.get("status") != "OK":
            return False

        return any(
            s.get("verdict") == "OK"
            and str(s["problem"].get("contestId")) == contest_id
            and s["problem"].get("index", "").upper() == problem_index
            and s.get("creationTimeSeconds", 0) >= after_ts
            for s in data["result"]
        )
