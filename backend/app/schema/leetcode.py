from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, computed_field

LEETCODE_PROBLEM_URL = "https://leetcode.com/problems/{slug}/"


class Difficulty(str, Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"

    @classmethod
    def _missing_(cls, value: object) -> "Difficulty | None":
        # LeetCode returns "Easy"/"EASY" depending on the query, and clients send lowercase
        if isinstance(value, str):
            return cls.__members__.get(value.upper())
        return None


class LeetCodeProblem(BaseModel):
    """A single free LeetCode problem, built from the camelCase dicts returned by LeetCodeService."""

    model_config = ConfigDict(populate_by_name=True)

    question_frontend_id: str = Field(validation_alias="questionFrontendId", description="The problem number shown on LeetCode")
    title: str = Field(description="Human readable problem title")
    title_slug: str = Field(validation_alias="titleSlug", description="Slug used in the problem URL")
    difficulty: Difficulty
    is_paid_only: bool = Field(default=False, validation_alias="isPaidOnly", description="Always false; premium problems are filtered out")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def url(self) -> str:
        return LEETCODE_PROBLEM_URL.format(slug=self.title_slug)


class ProblemListResponse(BaseModel):
    """One page of free problems matching the requested filters."""

    difficulty: Difficulty
    tags: list[str]
    skip: int = Field(description="Offset used for this page")
    limit: int = Field(description="Page size requested from LeetCode")
    total: int = Field(description="Total problems matching the filters on LeetCode, including premium ones")
    count: int = Field(description="Number of free problems in this page")
    problems: list[LeetCodeProblem]


class RandomProblemsResponse(BaseModel):
    """The problems drawn for a random-draw request."""

    difficulty: Difficulty
    tags: list[str]
    count: int = Field(description="Number of problems drawn; always equals the requested count")
    problems: list[LeetCodeProblem]


class UserExistsResponse(BaseModel):
    username: str
    exists: bool


class UserSolvedStatsResponse(BaseModel):
    """Accepted-problem counts per difficulty for a LeetCode user."""

    username: str
    easy: int
    medium: int
    hard: int

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total(self) -> int:
        return self.easy + self.medium + self.hard


class ProblemSolvedResponse(BaseModel):
    """Whether a user has an accepted submission for a problem after a given time."""

    username: str
    title_slug: str
    after: datetime
    solved: bool
