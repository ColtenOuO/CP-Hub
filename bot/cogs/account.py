import discord
from discord import app_commands
from discord.ext import commands

from backend.app.core.db import AsyncSessionLocal
from backend.app.crud.user import LeetCodeIDAlreadyLinkedError, upsert_leetcode_link
from backend.app.services.leetcode.client import LeetCodeService


class LinkGroup(app_commands.Group):
    def __init__(self, leetcode_service: LeetCodeService):
        super().__init__(name="link", description="Link your competitive programming accounts.")
        self.leetcode_service = leetcode_service

    @app_commands.command(name="leetcode", description="Link your LeetCode account to your Discord account.")
    @app_commands.describe(username="Your LeetCode username")
    async def leetcode(self, interaction: discord.Interaction, username: str):
        await interaction.response.defer(ephemeral=True)

        try:
            if not await self.leetcode_service.user_exists(username):
                await interaction.followup.send(f"找不到 LeetCode 帳號 `{username}`，請確認帳號名稱是否正確。")
                return

            async with AsyncSessionLocal() as session:
                try:
                    await upsert_leetcode_link(
                        session,
                        discord_id=interaction.user.id,
                        username=interaction.user.name,
                        leetcode_id=username,
                    )
                except LeetCodeIDAlreadyLinkedError:
                    await interaction.followup.send(f"LeetCode 帳號 `{username}` 已被其他使用者連結。")
                    return

            await interaction.followup.send(f"已成功將 LeetCode 帳號 `{username}` 連結到你的 Discord 帳號！")
        except Exception as exc:
            await interaction.followup.send(f"連結失敗：{exc}")


class Account(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.link_group = LinkGroup(LeetCodeService())
        bot.tree.add_command(self.link_group)

    async def cog_unload(self):
        self.bot.tree.remove_command(self.link_group.name)


async def setup(bot: commands.Bot):
    await bot.add_cog(Account(bot))
