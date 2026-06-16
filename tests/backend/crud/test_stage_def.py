import pytest

from backend.app.core.db import AsyncSessionLocal
from backend.app.crud.stage_def import (
    ProblemIndexError,
    StageNotFoundError,
    add_problem,
    create_stage,
    delete_stage,
    get_all_stages,
    get_stage,
    remove_problem,
    set_requires,
)

PROBLEM = {
    "url": "https://leetcode.com/problems/two-sum/",
    "title": "Two Sum",
    "platform": "leetcode",
    "rewards": {"exp": 50, "coins": 25},
}


@pytest.fixture(autouse=True)
async def cleanup():
    yield
    async with AsyncSessionLocal() as session:
        for stage in await get_all_stages(session):
            await session.delete(stage)
        await session.commit()


# ── create / get ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_stage():
    async with AsyncSessionLocal() as session:
        stage = await create_stage(session, name="Test Stage", rewards_exp=100, rewards_coins=50)

    assert stage.id is not None
    assert stage.name == "Test Stage"
    assert stage.rewards_exp == 100
    assert stage.rewards_coins == 50
    assert stage.requires == []
    assert stage.problems == []


@pytest.mark.asyncio
async def test_get_stage_found():
    async with AsyncSessionLocal() as session:
        created = await create_stage(session, name="Findable", rewards_exp=0, rewards_coins=0)

    async with AsyncSessionLocal() as session:
        stage = await get_stage(session, created.id)

    assert stage is not None
    assert stage.name == "Findable"


@pytest.mark.asyncio
async def test_get_stage_not_found():
    async with AsyncSessionLocal() as session:
        result = await get_stage(session, 999999)
    assert result is None


@pytest.mark.asyncio
async def test_get_all_stages_empty():
    async with AsyncSessionLocal() as session:
        result = await get_all_stages(session)
    assert result == []


@pytest.mark.asyncio
async def test_get_all_stages_multiple():
    async with AsyncSessionLocal() as session:
        await create_stage(session, name="Stage A", rewards_exp=0, rewards_coins=0)
        await create_stage(session, name="Stage B", rewards_exp=0, rewards_coins=0)

    async with AsyncSessionLocal() as session:
        result = await get_all_stages(session)

    assert len(result) == 2
    names = {s.name for s in result}
    assert names == {"Stage A", "Stage B"}


# ── delete ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_stage_success():
    async with AsyncSessionLocal() as session:
        stage = await create_stage(session, name="To Delete", rewards_exp=0, rewards_coins=0)

    async with AsyncSessionLocal() as session:
        deleted = await delete_stage(session, stage.id)

    assert deleted is True

    async with AsyncSessionLocal() as session:
        assert await get_stage(session, stage.id) is None


@pytest.mark.asyncio
async def test_delete_stage_not_found():
    async with AsyncSessionLocal() as session:
        result = await delete_stage(session, 999999)
    assert result is False


# ── set_requires ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_requires():
    async with AsyncSessionLocal() as session:
        s1 = await create_stage(session, name="S1", rewards_exp=0, rewards_coins=0)
        s2 = await create_stage(session, name="S2", rewards_exp=0, rewards_coins=0)

    async with AsyncSessionLocal() as session:
        updated = await set_requires(session, s2.id, [s1.id])

    assert updated.requires == [s1.id]


@pytest.mark.asyncio
async def test_set_requires_clear():
    async with AsyncSessionLocal() as session:
        s1 = await create_stage(session, name="S1", rewards_exp=0, rewards_coins=0)
        s2 = await create_stage(session, name="S2", rewards_exp=0, rewards_coins=0)
        await set_requires(session, s2.id, [s1.id])

    async with AsyncSessionLocal() as session:
        updated = await set_requires(session, s2.id, [])

    assert updated.requires == []


@pytest.mark.asyncio
async def test_set_requires_not_found():
    async with AsyncSessionLocal() as session:
        with pytest.raises(StageNotFoundError):
            await set_requires(session, 999999, [1])


# ── add_problem ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_problem():
    async with AsyncSessionLocal() as session:
        stage = await create_stage(session, name="With Problem", rewards_exp=0, rewards_coins=0)

    async with AsyncSessionLocal() as session:
        updated = await add_problem(session, stage.id, PROBLEM)

    assert len(updated.problems) == 1
    assert updated.problems[0]["title"] == "Two Sum"


@pytest.mark.asyncio
async def test_add_problem_appends():
    async with AsyncSessionLocal() as session:
        stage = await create_stage(session, name="Multi", rewards_exp=0, rewards_coins=0)

    problem2 = {**PROBLEM, "title": "Valid Parentheses"}
    async with AsyncSessionLocal() as session:
        await add_problem(session, stage.id, PROBLEM)
        updated = await add_problem(session, stage.id, problem2)

    assert len(updated.problems) == 2
    assert updated.problems[0]["title"] == "Two Sum"
    assert updated.problems[1]["title"] == "Valid Parentheses"


@pytest.mark.asyncio
async def test_add_problem_not_found():
    async with AsyncSessionLocal() as session:
        with pytest.raises(StageNotFoundError):
            await add_problem(session, 999999, PROBLEM)


# ── remove_problem ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_remove_problem():
    async with AsyncSessionLocal() as session:
        stage = await create_stage(session, name="Remove", rewards_exp=0, rewards_coins=0)
        await add_problem(session, stage.id, PROBLEM)

    async with AsyncSessionLocal() as session:
        updated = await remove_problem(session, stage.id, 0)

    assert updated.problems == []


@pytest.mark.asyncio
async def test_remove_problem_middle():
    async with AsyncSessionLocal() as session:
        stage = await create_stage(session, name="Remove Mid", rewards_exp=0, rewards_coins=0)
        for title in ["A", "B", "C"]:
            await add_problem(session, stage.id, {**PROBLEM, "title": title})

    async with AsyncSessionLocal() as session:
        updated = await remove_problem(session, stage.id, 1)

    assert len(updated.problems) == 2
    assert updated.problems[0]["title"] == "A"
    assert updated.problems[1]["title"] == "C"


@pytest.mark.asyncio
async def test_remove_problem_out_of_range():
    async with AsyncSessionLocal() as session:
        stage = await create_stage(session, name="OOB", rewards_exp=0, rewards_coins=0)
        await add_problem(session, stage.id, PROBLEM)

    async with AsyncSessionLocal() as session:
        with pytest.raises(ProblemIndexError):
            await remove_problem(session, stage.id, 5)


@pytest.mark.asyncio
async def test_remove_problem_not_found():
    async with AsyncSessionLocal() as session:
        with pytest.raises(StageNotFoundError):
            await remove_problem(session, 999999, 0)
