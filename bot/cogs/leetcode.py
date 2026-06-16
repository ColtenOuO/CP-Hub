from pathlib import Path
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from backend.app.services.leetcode.client import LeetCodeService

SOLUTION_THUMBNAIL_PATH = Path(__file__).resolve().parent.parent.parent / "static" / "images" / "LeetCode_logo_black.png"


class LeetCodeBot(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.leetcode_service = LeetCodeService()

    @app_commands.command(name="leetcode", description="Draw a random LeetCode problem based on tags and difficulty.")
    @app_commands.describe(tag="Topic tag to filter by", difficulty="Difficulty level (easy, medium, hard)")
    @app_commands.choices(
        difficulty=[
            app_commands.Choice(name="Easy 簡單", value="EASY"),
            app_commands.Choice(name="Medium 中等", value="MEDIUM"),
            app_commands.Choice(name="Hard 困難", value="HARD"),
        ],
        tag=[
            app_commands.Choice(name="Dynamic Programming (動態規劃)", value="dynamic-programming"),
            app_commands.Choice(name="Two Pointers (雙指標)", value="two-pointers"),
            app_commands.Choice(name="Tree / Binary Tree (樹與二元樹)", value="tree"),
            app_commands.Choice(name="Graph (圖論)", value="graph"),
            app_commands.Choice(name="Binary Search (二分搜尋)", value="binary-search"),
            app_commands.Choice(name="Greedy (貪婪演算法)", value="greedy"),
            app_commands.Choice(name="Sorting (排序)", value="sorting"),
            app_commands.Choice(name="Linked List (鏈結串列)", value="linked-list"),
            app_commands.Choice(name="Array (陣列)", value="array"),
            app_commands.Choice(name="String (字串)", value="string"),
            app_commands.Choice(name="Hash Table (雜湊表)", value="hash-table"),
            app_commands.Choice(name="Stack / Queue (堆疊/隊列)", value="stack"),
            app_commands.Choice(name="DFS / BFS (深度/廣度優先搜尋)", value="depth-first-search"),
            app_commands.Choice(name="Backtracking (回溯法)", value="backtracking"),
            app_commands.Choice(name="Bit Manipulation (位元運算)", value="bit-manipulation"),
            app_commands.Choice(name="Math (數學題)", value="math"),
        ],
    )
    async def draw_problem(self, interaction: discord.Interaction, difficulty: app_commands.Choice[str], tag: Optional[app_commands.Choice[str]] = None):
        await interaction.response.defer()
        try:
            tags = [tag.value] if tag else []
            problem = await self.leetcode_service.draw_random_problem(tags=tags, difficulty=difficulty.value)

            color_map = {"EASY": discord.Color.green(), "MEDIUM": discord.Color.orange(), "HARD": discord.Color.red()}
            card_color = color_map.get(difficulty.value, discord.Color.blue())
            embed = discord.Embed(title=f"{problem['title']}", url=problem["url"], color=card_color)
            embed.set_thumbnail(url="attachment://LeetCode_logo_black.png")
            embed.add_field(name="題目編號", value=problem["questionFrontendId"], inline=True)
            embed.add_field(name="難度", value=difficulty.name, inline=True)
            embed.add_field(name="分類標籤", value="||" + tag.name + "||" if tag else "不限", inline=True)
            embed.add_field(name="抽題者", value=interaction.user.mention, inline=True)

            file = discord.File(SOLUTION_THUMBNAIL_PATH, filename="LeetCode_logo_black.png")
            await interaction.followup.send(embed=embed, file=file)
        except Exception as exc:
            await interaction.followup.send(f"抽題失敗：{exc}")


async def setup(bot: commands.Bot):
    await bot.add_cog(LeetCodeBot(bot))
