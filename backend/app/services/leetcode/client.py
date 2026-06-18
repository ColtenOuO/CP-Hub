import random
from datetime import datetime
from typing import Any, Dict, List

import httpx

from backend.app.services.leetcode.queries import (
    LEETCODE_PROBLEM_LIST_QUERY,
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
    
    async def get_problem_list(self, tags: List[str], difficulty: str, limit: int = 100, skip: int = 0) -> List[Dict[str, Any]]:
        """Fetches a list of LeetCode problems based on specified tags and difficulty."""

        variables = {
            "categorySlug": "",
            "skip": skip,
            "limit": limit,
            "filters": {
                "filterCombineType": "ALL",
                "difficultyFilter": {
                    "difficulties": [difficulty.upper()],
                    "operator": "IS",
                },
                "topicFilter": {
                    "topicSlugs": tags,
                    "operator": "IS",
                },
            },
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
                    raise RuntimeError(
                        f"LeetCode server returned error {response.status_code}: {response.text}"
                    )

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

    async def draw_random_problem(self, tags: List[str], difficulty: str, choosing_window_size: int = 100, max_skip: int = 3000,) -> Dict[str, Any]:
        """Draws a random LeetCode problem based on specified tags and difficulty, ensuring it's free to access."""
        for _ in range(5):
            skip = random.randint(0, max_skip)

            questions = await self.get_problem_list(
                tags=tags,
                difficulty=difficulty,
                limit=choosing_window_size,
                skip=skip,
            )

            if questions:
                chosen_problem = random.choice(questions)
                chosen_problem["url"] = f"https://leetcode.com/problems/{chosen_problem['titleSlug']}/"
                return chosen_problem

        questions = await self.get_problem_list(
            tags=tags,
            difficulty=difficulty,
            limit=choosing_window_size,
            skip=0,
        )

        if not questions:
            raise ValueError(f"No free problems found for tags: {tags} and difficulty: {difficulty}")

        chosen_problem = random.choice(questions)

        chosen_problem["url"] = f"https://leetcode.com/problems/{chosen_problem['titleSlug']}/"

        return chosen_problem
