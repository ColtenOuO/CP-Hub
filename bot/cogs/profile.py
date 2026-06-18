import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from backend.app.core.db import AsyncSessionLocal
from backend.app.crud.platform_stats import get_cache_by_user_id
from backend.app.crud.stage import get_all_progress
from backend.app.crud.user import get_user_by_discord_id
from backend.app.models.platform_stats_cache import PlatformStatsCache
from backend.app.services.atcoder.client import AtCoderService
from backend.app.services.codeforces.client import CodeforcesService
from backend.app.services.leetcode.client import LeetCodeService
from backend.app.services.level import exp_progress


class Profile(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.leetcode_service = LeetCodeService()
        self.codeforces_service = CodeforcesService()
        self.atcoder_service = AtCoderService()

    @app_commands.command(name="profile", description="View your CP-Hub profile card.")
    async def profile(self, interaction: discord.Interaction):
        await interaction.response.defer()

        async with AsyncSessionLocal() as session:
            user = await get_user_by_discord_id(session, interaction.user.id)

            if user is None:
                await interaction.followup.send("尚未建立帳號資料，請先使用 `/link leetcode <username>` 連結帳號。")
                return

            level = user.stats.level
            exp = user.stats.exp
            coins = user.stats.coins
            leetcode_id = user.leetcode_id
            codeforces_id = user.codeforces_id
            atcoder_id = user.atcoder_id

            cache = await get_cache_by_user_id(session, user.id)
            progress = await get_all_progress(session, user.id)

        completed_stages = sum(1 for p in progress if p.is_completed)

        leetcode_field, codeforces_field, atcoder_field = await asyncio.gather(
            self._leetcode_field(leetcode_id),
            self._codeforces_field(codeforces_id, cache),
            self._atcoder_field(atcoder_id),
        )

        current_exp, needed_exp, _ = exp_progress(exp)
        filled = round(current_exp / needed_exp * 10)
        bar = "█" * filled + "░" * (10 - filled)
        pct = int(current_exp / needed_exp * 100)

        embed = discord.Embed(title=f"{interaction.user.display_name} 的個人檔案", color=discord.Color.gold())
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="等級", value=str(level), inline=True)
        embed.add_field(name="金幣", value=str(coins), inline=True)
        embed.add_field(name="完成關卡數量", value=str(completed_stages), inline=True)
        embed.add_field(name="LeetCode", value=leetcode_field, inline=True)
        embed.add_field(name="Codeforces", value=codeforces_field, inline=True)
        embed.add_field(name="AtCoder", value=atcoder_field, inline=True)
        embed.add_field(
            name=f"經驗值　Lv.{level} → Lv.{level + 1}",
            value=f"`{bar}` {current_exp} / {needed_exp} EXP　（{pct}%）",
            inline=False,
        )

        await interaction.followup.send(embed=embed)

    async def _leetcode_field(self, leetcode_id: str | None) -> str:
        if leetcode_id is None:
            return "未連結"

        try:
            stats = await self.leetcode_service.get_solved_stats(leetcode_id)
        except RuntimeError:
            return "讀取失敗"

        if stats is None:
            return "讀取失敗"

        total = stats["easy"] + stats["medium"] + stats["hard"]
        return f"共 {total} 題\nEasy: {stats['easy']}\nMedium: {stats['medium']}\nHard: {stats['hard']}"

    async def _codeforces_field(self, codeforces_id: str | None, cache: PlatformStatsCache | None) -> str:
        if codeforces_id is None:
            return "未連結"

        try:
            rating = await self.codeforces_service.get_rating(codeforces_id)
            rating_text = str(rating) if rating is not None else "Unrated"
        except RuntimeError:
            rating_text = "讀取失敗"

        solved_text = f"{cache.codeforces_solved} 題" if cache is not None and cache.codeforces_solved is not None else "尚未同步"
        return f"Rating: {rating_text}\n解題數: {solved_text}"

    async def _atcoder_field(self, atcoder_id: str | None) -> str:
        if atcoder_id is None:
            return "未連結"

        try:
            rating = await self.atcoder_service.get_rating(atcoder_id)
        except RuntimeError:
            return "讀取失敗"

        return str(rating) if rating is not None else "Unrated"


async def setup(bot: commands.Bot):
    await bot.add_cog(Profile(bot))
