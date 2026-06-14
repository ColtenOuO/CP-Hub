import random
from typing import Any, Dict, List

import httpx

from backend.app.services.leetcode.queries import LEETCODE_PROBLEM_LIST_QUERY


class LeetCodeService:
    def __init__(self):
        self.graphql_url = "https://leetcode.com/graphql"
        self.headers = {
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

    async def get_problem_list(self, tags: List[str], difficulty: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetches a list of LeetCode problems based on specified tags and difficulty."""

        variables = {
            "categorySlug": "",
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
                    raise httpx.HTTPStatusError(
                        f"LeetCode server returned error: {response.status_code}",
                        request=response.request,
                        response=response,
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

    async def draw_random_problem(self, tags: List[str], difficulty: str) -> Dict[str, Any]:
        """Draws a random LeetCode problem based on specified tags and difficulty, ensuring it's free to access."""
        questions = await self.get_problem_list(tags, difficulty)

        if not questions:
            raise ValueError(f"No free problems found for tags: {tags} and difficulty: {difficulty}")

        chosen_problem = random.choice(questions)

        chosen_problem["url"] = f"https://leetcode.com/problems/{chosen_problem['titleSlug']}/"

        return chosen_problem
