import logging
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from backend.app.core.config import settings
from backend.app.core.db import AsyncSessionLocal
from backend.app.crud.group_task import get_active_task
from backend.app.crud.user import get_user_by_discord_id
from backend.app.models.group_task import GroupTask
from backend.app.models.group_task_problem import GroupTaskProblem
from backend.app.services.group_task.service import (
    ActiveTaskExistsError,
    GroupTaskService,
    NoActiveTaskError,
    RecapData,
)
from backend.app.services.leetcode.client import LeetCodeService

logger = logging.getLogger(__name__)

TASK_TIMEZONE = timezone(timedelta(hours=8))
EXPIRY_CHECK_INTERVAL_MINUTES = 1

DIFFICULTY_COLOR = {"easy": discord.Color.green(), "medium": discord.Color.orange(), "hard": discord.Color.red()}
DIFFICULTY_LABEL = {"easy": "Easy", "medium": "Medium", "hard": "Hard"}


def _is_admin(discord_id: int) -> bool:
    return discord_id in settings.admin_discord_ids


def _parse_codes(raw: str) -> list[str]:
    return [code.strip().upper() for code in raw.split(",") if code.strip()]


def _parse_deadline(raw: str) -> datetime:
    naive = datetime.strptime(raw, "%Y-%m-%d %H:%M")
    return naive.replace(tzinfo=TASK_TIMEZONE).astimezone(timezone.utc)


def _sorted_problems(task: GroupTask, difficulty: str) -> list[GroupTaskProblem]:
    return sorted((p for p in task.problems if p.difficulty == difficulty), key=lambda p: int(p.code[1:]))


def _build_rules_embed(task: GroupTask) -> discord.Embed:
    deadline_text = discord.utils.format_dt(task.deadline, style="F")
    embed = discord.Embed(
        title="📢 群組任務開始！",
        description=(
            f"截止時間：{deadline_text}\n\n"
            "**指令**\n"
            "`/grouptask claim codes:E1,M3,...` 認領題目（可一次認領多題）\n"
            "`/grouptask unclaim codes:...` 取消認領\n"
            "`/grouptask verify` 驗證已認領的題目（會列出你認領中的題目供選擇）\n"
            "`/grouptask status` 查看目前所有題目認領/完成狀態\n\n"
            "**每題固定獎勵**\nEasy：10 金幣 / 30 EXP\nMedium：30 金幣 / 55 EXP\nHard：100 金幣 / 150 EXP\n\n"
            f"**全部完成加成獎勵**（發給每位有貢獻的人）\n{task.reward_exp} EXP / {task.reward_coins} 金幣\n\n"
            "⚠️ 請先認領再解題：驗證只承認「認領之後」的 AC 紀錄，且只會檢查最近 20 筆 AC，請盡快回來驗證。"
        ),
        color=discord.Color.gold(),
    )
    embed.set_thumbnail(url="attachment://LeetCode_logo_black.png")
    return embed


def _build_problem_list_embed(task: GroupTask, difficulty: str) -> discord.Embed:
    embed = discord.Embed(title=f"{DIFFICULTY_LABEL[difficulty]} 題目", color=DIFFICULTY_COLOR[difficulty])
    for problem in _sorted_problems(task, difficulty):
        embed.add_field(name=problem.code, value=f"[{problem.title}]({problem.url})", inline=False)
    return embed


def _build_status_embed(task: GroupTask) -> discord.Embed:
    embed = discord.Embed(title="群組任務目前狀態", color=discord.Color.blue())
    for difficulty in ("easy", "medium", "hard"):
        lines = []
        for problem in _sorted_problems(task, difficulty):
            problem_link = f"[{problem.title}]({problem.url})"

            if problem.is_completed:
                claimant = problem.completed_by_user.username if problem.completed_by_user else "?"
                lines.append(f"✅ {problem.code} {problem_link} — {claimant}")
            elif problem.claimed_by is not None:
                claimant = problem.claimed_by_user.username if problem.claimed_by_user else "?"
                lines.append(f"🔵 {problem.code} {problem_link} — {claimant}（認領中）")
            else:
                lines.append(f"⬜ {problem.code} {problem_link} — 尚無人認領")
        embed.add_field(name=DIFFICULTY_LABEL[difficulty], value="\n".join(lines), inline=False)
    return embed


def _build_recap_embed(recap: RecapData) -> discord.Embed:
    if recap.status == "completed":
        title, color = "🎉 群組任務完成！", discord.Color.gold()
    else:
        title, color = "⌛ 群組任務已過期失敗", discord.Color.dark_grey()

    lines = [f"完成題數：{recap.completed_problems}/{recap.total_problems}", ""]
    if recap.entries:
        for i, entry in enumerate(recap.entries, start=1):
            c = entry.counts
            lines.append(f"**{i}. {entry.user.username}** — Easy:{c['easy']} Medium:{c['medium']} Hard:{c['hard']}（共 {entry.total} 題）")
    else:
        lines.append("（沒有人完成任何題目）")

    if recap.status == "completed":
        lines.append("")
        lines.append(f"🎁 加成獎勵：每位貢獻者 +{recap.bonus_exp} EXP / +{recap.bonus_coins} 金幣")

    return discord.Embed(title=title, description="\n".join(lines), color=color)


class VerifySelect(discord.ui.Select):
    def __init__(self, cog: "GroupTaskCog", problems: list[GroupTaskProblem]):
        options = [discord.SelectOption(label=f"{p.code} {p.title}"[:100], value=p.code) for p in problems[:25]]
        super().__init__(placeholder="選擇要驗證的題目（可多選）", min_values=1, max_values=len(options), options=options)
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.cog.handle_verify_selection(interaction, self.values)


class VerifyView(discord.ui.View):
    def __init__(self, cog: "GroupTaskCog", problems: list[GroupTaskProblem]):
        super().__init__(timeout=300)
        self.message: discord.Message | None = None
        self.add_item(VerifySelect(cog, problems))

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class GroupTaskCog(commands.Cog):
    admin_group = app_commands.Group(name="admin", description="群組任務管理（限管理員）")
    task_group = app_commands.Group(name="grouptask", description="群組任務")
    task_group.add_command(admin_group)

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.service = GroupTaskService(LeetCodeService())

    async def cog_load(self):
        self.expiry_check_loop.start()

    def cog_unload(self):
        self.expiry_check_loop.cancel()

    @tasks.loop(minutes=EXPIRY_CHECK_INTERVAL_MINUTES)
    async def expiry_check_loop(self):
        try:
            async with AsyncSessionLocal() as session:
                task = await get_active_task(session)
                if task is None or task.deadline > datetime.now(timezone.utc):
                    return
                recap = await self.service.finalize(session, task.id, "expired")

            if recap is not None:
                channel = self.bot.get_channel(task.channel_id)
                if channel is not None:
                    await channel.send(embed=_build_recap_embed(recap))
        except Exception:
            logger.exception("Group task expiry check failed")

    @expiry_check_loop.error
    async def expiry_check_loop_error(self, error: Exception):
        logger.exception("Group task expiry loop crashed", exc_info=error)

    async def handle_verify_selection(self, interaction: discord.Interaction, codes: list[str]):
        async with AsyncSessionLocal() as session:
            task = await get_active_task(session)
            if task is None:
                await interaction.followup.send("此任務已結束。", ephemeral=True)
                return

            user = await get_user_by_discord_id(session, interaction.user.id)
            if user is None:
                await interaction.followup.send("找不到你的帳號。", ephemeral=True)
                return

            result = await self.service.verify(session, task, user, codes)

            if result.succeeded:
                lines = [
                    f"🎉 {interaction.user.mention} 完成了 **{vp.problem.code} {vp.problem.title}**"
                    f"（{DIFFICULTY_LABEL[vp.problem.difficulty]}）！獲得 {vp.exp} EXP / {vp.coins} 金幣！"
                    for vp in result.succeeded
                ]
                await interaction.followup.send("\n".join(lines), ephemeral=False)

            if result.failed:
                lines = [f"`{fp.code}`：{fp.reason}" for fp in result.failed]
                await interaction.followup.send("以下題目驗證失敗：\n" + "\n".join(lines), ephemeral=True)

            recap = None
            if result.task_completed:
                recap = await self.service.finalize(session, task.id, "completed")

        if recap is not None:
            channel = self.bot.get_channel(task.channel_id)
            if channel is not None:
                await channel.send(embed=_build_recap_embed(recap))

    @task_group.command(name="claim", description="認領群組任務題目（可一次認領多題，用逗號分隔）")
    @app_commands.describe(codes="題目代號，例如 E1,M3,H10")
    async def claim(self, interaction: discord.Interaction, codes: str):
        await interaction.response.defer(ephemeral=True)
        parsed_codes = _parse_codes(codes)
        async with AsyncSessionLocal() as session:
            task = await get_active_task(session)
            if task is None:
                await interaction.followup.send("目前沒有進行中的群組任務。", ephemeral=True)
                return

            user = await get_user_by_discord_id(session, interaction.user.id)
            if user is None:
                await interaction.followup.send("找不到你的帳號，請先使用 `/link leetcode <username>` 連結帳號。", ephemeral=True)
                return

            results = await self.service.claim(session, task, user, parsed_codes)

        lines = [f"`{code}`：{message}" for code, message in results.items()]
        await interaction.followup.send("\n".join(lines), ephemeral=True)

    @task_group.command(name="unclaim", description="取消認領群組任務題目（可一次取消多題，用逗號分隔）")
    @app_commands.describe(codes="題目代號，例如 E1,M3,H10")
    async def unclaim(self, interaction: discord.Interaction, codes: str):
        await interaction.response.defer(ephemeral=True)
        parsed_codes = _parse_codes(codes)
        async with AsyncSessionLocal() as session:
            task = await get_active_task(session)
            if task is None:
                await interaction.followup.send("目前沒有進行中的群組任務。", ephemeral=True)
                return

            user = await get_user_by_discord_id(session, interaction.user.id)
            if user is None:
                await interaction.followup.send("找不到你的帳號，請先使用 `/link leetcode <username>` 連結帳號。", ephemeral=True)
                return

            results = await self.service.unclaim(session, task, user, parsed_codes)

        lines = [f"`{code}`：{message}" for code, message in results.items()]
        await interaction.followup.send("\n".join(lines), ephemeral=True)

    @task_group.command(name="verify", description="驗證已認領的題目")
    async def verify(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        async with AsyncSessionLocal() as session:
            task = await get_active_task(session)
            if task is None:
                await interaction.followup.send("目前沒有進行中的群組任務。", ephemeral=True)
                return

            user = await get_user_by_discord_id(session, interaction.user.id)
            if user is None:
                await interaction.followup.send("找不到你的帳號，請先使用 `/link leetcode <username>` 連結帳號。", ephemeral=True)
                return

            problems = await self.service.get_verifiable_problems(session, task, user)

        if not problems:
            await interaction.followup.send("你目前沒有認領中尚未完成的題目，請先用 `/grouptask claim` 認領題目。", ephemeral=True)
            return

        view = VerifyView(self, problems)
        message = await interaction.followup.send("請選擇要驗證的題目：", view=view, ephemeral=True)
        view.message = message

    @task_group.command(name="status", description="查看目前群組任務狀態")
    async def status(self, interaction: discord.Interaction):
        await interaction.response.defer()
        async with AsyncSessionLocal() as session:
            task = await get_active_task(session)

        if task is None:
            await interaction.followup.send("目前沒有進行中的群組任務。")
            return

        await interaction.followup.send(embed=_build_status_embed(task))

    @admin_group.command(name="create", description="建立群組任務（抽 10 Easy/10 Medium/10 Hard 題）")
    @app_commands.describe(
        deadline="截止時間，格式 YYYY-MM-DD HH:MM（台灣時間）",
        reward_exp="全部完成後每位貢獻者獲得的 EXP",
        reward_coins="全部完成後每位貢獻者獲得的金幣",
    )
    async def admin_create(self, interaction: discord.Interaction, deadline: str, reward_exp: int, reward_coins: int):
        if not _is_admin(interaction.user.id):
            await interaction.response.send_message("你沒有權限執行此指令。", ephemeral=True)
            return

        try:
            parsed_deadline = _parse_deadline(deadline)
        except ValueError:
            await interaction.response.send_message("截止時間格式錯誤，請使用 `YYYY-MM-DD HH:MM`（台灣時間）。", ephemeral=True)
            return

        await interaction.response.defer()

        async with AsyncSessionLocal() as session:
            try:
                task = await self.service.create_task(
                    session,
                    deadline=parsed_deadline,
                    reward_exp=reward_exp,
                    reward_coins=reward_coins,
                    created_by=interaction.user.id,
                    channel_id=interaction.channel_id,
                )
            except ActiveTaskExistsError:
                await interaction.followup.send("已經有一個進行中的群組任務，請先用 `/grouptask admin delete` 結束它。", ephemeral=True)
                return

        file = discord.File("static/images/LeetCode_logo_black.png", filename="LeetCode_logo_black.png")
        embeds = [_build_rules_embed(task)] + [_build_problem_list_embed(task, difficulty) for difficulty in ("easy", "medium", "hard")]
        await interaction.followup.send(embeds=embeds, file=file)

    @admin_group.command(name="delete", description="刪除目前進行中的群組任務")
    async def admin_delete(self, interaction: discord.Interaction):
        if not _is_admin(interaction.user.id):
            await interaction.response.send_message("你沒有權限執行此指令。", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        async with AsyncSessionLocal() as session:
            try:
                await self.service.delete_active_task(session)
            except NoActiveTaskError:
                await interaction.followup.send("目前沒有進行中的群組任務。", ephemeral=True)
                return

        await interaction.followup.send("已刪除目前的群組任務。", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(GroupTaskCog(bot))
