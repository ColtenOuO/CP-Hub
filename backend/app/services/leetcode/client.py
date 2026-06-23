import random
from datetime import datetime
from typing import Any, Dict, List

import httpx

from backend.app.services.leetcode.queries import (
    LEETCODE_PROBLEM_LIST_QUERY,
    LEETCODE_PROBLEM_TOTAL_QUERY,
    LEETCODE_RECENT_AC_SUBMISSIONS_QUERY,
    LEETCODE_USER_PROFILE_QUERY,
    LEETCODE_USER_SOLVED_STATS_QUERY,
)


class LeetCodeService:
    def __init__(self):
        self.graphql_url = "https://leetcode.com/graphql"
        self.headers = {
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

    async def get_problem_total(self, tags: List[str], difficulty: str) -> int:
        """Fetches the total number of LeetCode problems matching the given tags and difficulty."""

        filters = {
            "difficulty": difficulty.upper(),
        }

        if tags:
            filters["tags"] = tags

        variables = {
            "categorySlug": "",
            "skip": 0,
            "limit": 1,
            "filters": filters,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.graphql_url,
                    json={
                        "query": LEETCODE_PROBLEM_TOTAL_QUERY,
                        "variables": variables,
                    },
                    headers=self.headers,
                    timeout=10.0,
                )

                if response.status_code != 200:
                    raise RuntimeError(f"LeetCode server returned error {response.status_code}: {response.text}")

                data = response.json()

                if "errors" in data:
                    raise ValueError(f"GraphQL query error: {data['errors'][0]['message']}")

                return data["data"]["problemsetQuestionList"]["total"]

            except httpx.RequestError as exc:
                raise RuntimeError(f"Error occurred while fetching problem total: {exc}")

    async def get_problem_list(self, tags: List[str], difficulty: str, limit: int = 100, skip: int = 0) -> List[Dict[str, Any]]:
        """Fetches a list of LeetCode problems based on specified tags and difficulty."""

        filters = {
            "filterCombineType": "ALL",
            "difficultyFilter": {
                "difficulties": [difficulty.upper()],
                "operator": "IS",
            },
        }

        if tags:
            filters["topicFilter"] = {
                "topicSlugs": tags,
                "operator": "IS",
            }

        variables = {
            "categorySlug": "",
            "skip": skip,
            "limit": limit,
            "filters": filters,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.graphql_url,
                    json={"query": LEETCODE_PROBLEM_LIST_QUERY, "variables": variables},
                    headers=self.headers,
                    timeout=10.0,
                )

                if response.status_code != 200:
                    raise RuntimeError(f"LeetCode server returned error {response.status_code}: {response.text}")

                data = response.json()

                if "errors" in data:
                    raise ValueError(f"GraphQL query error: {data['errors'][0]['message']}")

                questions = data["data"]["problemsetQuestionListV2"]["questions"]
                free_questions = [
                    {
                        "questionFrontendId": q["questionFrontendId"],
                        "title": q["title"],
                        "titleSlug": q["titleSlug"],
                        "difficulty": q["difficulty"],
                        "isPaidOnly": q["paidOnly"],
                    }
                    for q in questions
                    if not q["paidOnly"]
                ]

                return free_questions

            except httpx.RequestError as exc:
                raise RuntimeError(f"Error occurred while fetching problem list: {exc}")

    async def user_exists(self, username: str) -> bool:
        """Checks whether a LeetCode account with the given username exists."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.graphql_url,
                    json={"query": LEETCODE_USER_PROFILE_QUERY, "variables": {"username": username}},
                    headers=self.headers,
                    timeout=10.0,
                )

                if response.status_code != 200:
                    raise httpx.HTTPStatusError(
                        f"LeetCode server returned error: {response.status_code}",
                        request=response.request,
                        response=response,
                    )

                data = response.json()
                return (data.get("data") or {}).get("matchedUser") is not None

            except httpx.RequestError as exc:
                raise RuntimeError(f"Error occurred while checking LeetCode user: {exc}")

    async def get_solved_stats(self, username: str) -> Dict[str, int] | None:
        """Fetches the number of solved problems per difficulty for the given LeetCode user."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.graphql_url,
                    json={"query": LEETCODE_USER_SOLVED_STATS_QUERY, "variables": {"username": username}},
                    headers=self.headers,
                    timeout=10.0,
                )

                if response.status_code != 200:
                    raise httpx.HTTPStatusError(
                        f"LeetCode server returned error: {response.status_code}",
                        request=response.request,
                        response=response,
                    )

                data = response.json()
                matched_user = (data.get("data") or {}).get("matchedUser")

                if matched_user is None:
                    return None

                counts = {item["difficulty"]: item["count"] for item in matched_user["submitStatsGlobal"]["acSubmissionNum"]}
                return {"easy": counts.get("Easy", 0), "medium": counts.get("Medium", 0), "hard": counts.get("Hard", 0)}

            except httpx.RequestError as exc:
                raise RuntimeError(f"Error occurred while fetching LeetCode solved stats: {exc}")

    async def verify_problem_solved(self, username: str, title_slug: str, after: datetime) -> bool:
        """Returns True if the user has an AC submission for title_slug after the given datetime."""
        after_ts = int(after.timestamp())
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.graphql_url,
                    json={
                        "query": LEETCODE_RECENT_AC_SUBMISSIONS_QUERY,
                        "variables": {"username": username, "limit": 20},
                    },
                    headers=self.headers,
                    timeout=10.0,
                )

                if response.status_code != 200:
                    raise httpx.HTTPStatusError(
                        f"LeetCode server returned error: {response.status_code}",
                        request=response.request,
                        response=response,
                    )

                data = response.json()
                submissions = (data.get("data") or {}).get("recentAcSubmissionList", [])
                return any(s["titleSlug"] == title_slug and int(s["timestamp"]) >= after_ts for s in submissions)

            except httpx.RequestError as exc:
                raise RuntimeError(f"Error occurred while verifying LeetCode submission: {exc}")

    async def draw_random_problems(
        self,
        difficulty: str,
        count: int = 1,
        tags: List[str] | None = None,
        choosing_window_size: int = 100,
        take_per_window: int = 1,
        max_attempts: int = 30,
    ) -> List[Dict[str, Any]]:
        """Draws up to `count` unique free LeetCode problems based on tags and difficulty."""

        tags = tags or []

        total = await self.get_problem_total(tags, difficulty)

        if total == 0:
            raise ValueError(f"No problems found for tags: {tags} and difficulty: {difficulty}")

        window_size = min(max(choosing_window_size, 1), total)
        max_skip = max(total - window_size, 0)

        chosen: list[Dict[str, Any]] = []
        seen_slugs: set[str] = set()
        attempts = 0

        while len(chosen) < count and attempts < max_attempts:
            attempts += 1
            skip = random.randint(0, max_skip)

            questions = await self.get_problem_list(
                tags=tags,
                difficulty=difficulty,
                limit=window_size,
                skip=skip,
            )

            if not questions:
                continue

            random.shuffle(questions)

            picked_from_this_window = 0

            for problem in questions:
                slug = problem["titleSlug"]

                if slug in seen_slugs:
                    continue

                problem["url"] = f"https://leetcode.com/problems/{slug}/"
                chosen.append(problem)
                seen_slugs.add(slug)

                picked_from_this_window += 1

                if len(chosen) >= count or picked_from_this_window >= take_per_window:
                    break

        if len(chosen) < count:
            raise ValueError(f"Only found {len(chosen)} free problems for tags: {tags} and difficulty: {difficulty}")

        return chosen

    async def draw_random_problem(
        self,
        difficulty: str,
        tags: List[str] | None = None,
        choosing_window_size: int = 100,
    ) -> Dict[str, Any]:
        """Draws one random free LeetCode problem."""

        problems = await self.draw_random_problems(
            tags=tags,
            difficulty=difficulty,
            count=1,
            choosing_window_size=choosing_window_size,
        )

        return problems[0]
