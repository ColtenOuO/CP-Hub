import logging
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands, tasks

from backend.app.core.config import settings
from backend.app.core.db import AsyncSessionLocal
from backend.app.crud.platform_stats import get_cache_by_user_id, get_top_by_codeforces, get_top_by_leetcode
from backend.app.crud.user import get_top_by_level, get_user_by_discord_id
from backend.app.services.codeforces.client import CodeforcesService
from backend.app.services.leetcode.client import LeetCodeService
from backend.app.services.sync.leaderboard_sync import LeaderboardSyncService

logger = logging.getLogger(__name__)

SYNC_INTERVAL_MINUTES = 5

MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}

BOARD_IMAGES = {
    "level": "static/images/trophy.png",
    "leetcode": "static/images/LeetCode_logo_black.png",
    "codeforces": "static/images/codeforces.jpg",
}


def _is_admin(discord_id: int) -> bool:
    return discord_id in settings.admin_discord_ids


def _format_board_description(entries: list[tuple[str, str]]) -> str:
    """Renders the top 3 entries as large headings (medal + name) and the rest as a plain numbered list."""
    podium, rest = entries[:3], entries[3:]

    podium_block = "\n\n".join(f"## {MEDALS[rank]}　{name}\n{value}" for rank, (name, value) in enumerate(podium, start=1))
    rest_block = "\n".join(f"**{rank}.** {name} — {value}" for rank, (name, value) in enumerate(rest, start=4))

    if not rest_block:
        return podium_block
    if not podium_block:
        return rest_block
    return f"{podium_block}\n\n────────────────\n{rest_block}"


def _attach_board_image(embed: discord.Embed, board: str) -> discord.File:
    path = BOARD_IMAGES[board]
    filename = Path(path).name
    embed.set_thumbnail(url=f"attachment://{filename}")
    return discord.File(path, filename=filename)


async def _build_level_embed() -> discord.Embed:
    async with AsyncSessionLocal() as session:
        users = await get_top_by_level(session, limit=10)

    embed = discord.Embed(title="等級排行榜", color=discord.Color.gold())
    if not users:
        embed.description = "目前還沒有任何使用者資料。"
        return embed

    entries = [(user.username, f"Lv.{user.stats.level}（{user.stats.coins} 金幣）") for user in users]
    embed.description = _format_board_description(entries)
    return embed


async def _build_leetcode_embed() -> discord.Embed:
    async with AsyncSessionLocal() as session:
        rows = await get_top_by_leetcode(session, limit=10)

    embed = discord.Embed(title="LeetCode 排行榜", color=discord.Color.orange())
    if not rows:
        embed.description = "目前還沒有任何已同步的 LeetCode 資料。"
        return embed

    entries = []
    for user, cache in rows:
        total = cache.leetcode_easy + cache.leetcode_medium + cache.leetcode_hard
        entries.append((user.username, f"共 {total} 題（E:{cache.leetcode_easy} M:{cache.leetcode_medium} H:{cache.leetcode_hard}）"))
    embed.description = _format_board_description(entries)
    embed.set_footer(text="資料每 5 分鐘自動同步一次")
    return embed


async def _build_codeforces_embed() -> discord.Embed:
    async with AsyncSessionLocal() as session:
        rows = await get_top_by_codeforces(session, limit=10)

    embed = discord.Embed(title="Codeforces 排行榜", color=discord.Color.blue())
    if not rows:
        embed.description = "目前還沒有任何已同步的 Codeforces 資料。"
        return embed

    entries = [(user.username, f"{cache.codeforces_solved} 題") for user, cache in rows]
    embed.description = _format_board_description(entries)
    embed.set_footer(text="資料每 5 分鐘自動同步一次")
    return embed


_BOARD_BUILDERS = {
    "level": _build_level_embed,
    "leetcode": _build_leetcode_embed,
    "codeforces": _build_codeforces_embed,
}


async def _build_board(board: str) -> tuple[discord.Embed, discord.File]:
    embed = await _BOARD_BUILDERS[board]()
    file = _attach_board_image(embed, board)
    return embed, file


class LeaderboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.current = "level"
        self._sync_button_styles()

    def _sync_button_styles(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.style = discord.ButtonStyle.primary if child.custom_id == self.current else discord.ButtonStyle.secondary

    async def _switch(self, interaction: discord.Interaction, board: str):
        self.current = board
        self._sync_button_styles()
        embed, file = await _build_board(board)
        await interaction.response.edit_message(embed=embed, attachments=[file], view=self)

    @discord.ui.button(label="等級榜", custom_id="level", style=discord.ButtonStyle.primary)
    async def level_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch(interaction, "level")

    @discord.ui.button(label="LeetCode 榜", custom_id="leetcode", style=discord.ButtonStyle.secondary)
    async def leetcode_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch(interaction, "leetcode")

    @discord.ui.button(label="Codeforces 榜", custom_id="codeforces", style=discord.ButtonStyle.secondary)
    async def codeforces_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch(interaction, "codeforces")


class LeaderboardCog(commands.Cog):
    admin_group = app_commands.Group(name="leaderboard-admin", description="排行榜管理（限管理員）")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sync_service = LeaderboardSyncService(LeetCodeService(), CodeforcesService())

    async def cog_load(self):
        self.sync_loop.start()

    def cog_unload(self):
        self.sync_loop.cancel()

    @tasks.loop(minutes=SYNC_INTERVAL_MINUTES)
    async def sync_loop(self):
        try:
            async with AsyncSessionLocal() as session:
                summary = await self.sync_service.sync_all(session)
            logger.info("Leaderboard sync complete: %s", summary)
        except Exception:
            logger.exception("Leaderboard sync loop failed")

    @sync_loop.error
    async def sync_loop_error(self, error: Exception):
        logger.exception("Leaderboard sync loop crashed", exc_info=error)

    @app_commands.command(name="leaderboard", description="查看伺服器排行榜")
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed, file = await _build_board("level")
        await interaction.followup.send(embed=embed, file=file, view=LeaderboardView())

    @app_commands.command(name="rank", description="查看你目前的排名狀態")
    async def rank(self, interaction: discord.Interaction):
        await interaction.response.defer()
        async with AsyncSessionLocal() as session:
            user = await get_user_by_discord_id(session, interaction.user.id)
            if user is None:
                await interaction.followup.send("尚未建立帳號資料，請先使用 `/link leetcode <username>` 連結帳號。")
                return

            cache = await get_cache_by_user_id(session, user.id)
            level = user.stats.level
            coins = user.stats.coins
            leetcode_id = user.leetcode_id
            codeforces_id = user.codeforces_id

        embed = discord.Embed(title=f"{interaction.user.display_name} 的排名狀態", color=discord.Color.green())
        embed.add_field(name="等級", value=str(level), inline=True)
        embed.add_field(name="金幣", value=str(coins), inline=True)
        embed.add_field(name="​", value="​", inline=True)

        if leetcode_id is None:
            leetcode_value = "未連結"
        elif cache is None or cache.leetcode_easy is None:
            leetcode_value = "已連結，等待下次同步"
        else:
            total = cache.leetcode_easy + cache.leetcode_medium + cache.leetcode_hard
            leetcode_value = f"共 {total} 題\nEasy: {cache.leetcode_easy}\nMedium: {cache.leetcode_medium}\nHard: {cache.leetcode_hard}"
        embed.add_field(name="LeetCode", value=leetcode_value, inline=True)

        if codeforces_id is None:
            codeforces_value = "未連結"
        elif cache is None or cache.codeforces_solved is None:
            codeforces_value = "已連結，等待下次同步"
        else:
            codeforces_value = f"{cache.codeforces_solved} 題"
        embed.add_field(name="Codeforces", value=codeforces_value, inline=True)

        await interaction.followup.send(embed=embed)

    @admin_group.command(name="sync", description="手動觸發一次排行榜資料同步")
    async def admin_sync(self, interaction: discord.Interaction):
        if not _is_admin(interaction.user.id):
            await interaction.response.send_message("你沒有權限執行此指令。", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        async with AsyncSessionLocal() as session:
            summary = await self.sync_service.sync_all(session)
        await interaction.followup.send(
            f"同步完成：LeetCode {summary['leetcode_ok']} 成功 / {summary['leetcode_failed']} 失敗，"
            f"Codeforces {summary['codeforces_ok']} 成功 / {summary['codeforces_failed']} 失敗。",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(LeaderboardCog(bot))
