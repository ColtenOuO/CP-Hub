import discord
from discord import app_commands
from discord.ext import commands

from backend.app.core.db import AsyncSessionLocal
from backend.app.crud.user import get_user_by_discord_id
from backend.app.services.leetcode.client import LeetCodeService
from backend.app.services.stage.graph import StageGraph
from backend.app.services.stage.service import (
    AlreadyEnrolledError,
    DependencyNotMetError,
    NoLeetCodeAccountError,
    NotEnrolledError,
    StageService,
)

stage_group = app_commands.Group(name="stage", description="關卡挑戰系統")

_PLATFORM_EMOJI = {"leetcode": "<:leetcode:0>"}


def _platform_label(platform: str) -> str:
    return platform.capitalize()


class VerifyView(discord.ui.View):
    def __init__(self, stage_id: int, original_user_id: int, service: StageService):
        super().__init__(timeout=300)
        self.stage_id = stage_id
        self.original_user_id = original_user_id
        self.service = service

    @discord.ui.button(label="完成驗證", style=discord.ButtonStyle.green, emoji="✅")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.original_user_id:
            await interaction.response.send_message("只有抽題者可以驗證！", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        async with AsyncSessionLocal() as session:
            user = await get_user_by_discord_id(session, interaction.user.id)
            if user is None:
                await interaction.followup.send("找不到你的帳號，請先用 `/account register` 註冊。", ephemeral=True)
                return

            try:
                result = await self.service.verify_and_advance(session, user, self.stage_id)
            except (NotEnrolledError, NoLeetCodeAccountError) as e:
                await interaction.followup.send(str(e), ephemeral=True)
                return

        if not result.solved:
            await interaction.followup.send(
                "尚未在 LeetCode 上看到你的 AC 提交，請確認已成功提交後再試一次。",
                ephemeral=True,
            )
            return

        lines = [
            f"獲得 **{result.problem_rewards['exp']} EXP** 和 **{result.problem_rewards['coins']} 金幣**！",
        ]

        if result.stage_complete:
            lines.append(f"🎉 關卡完成！額外獲得 **{result.stage_rewards['exp']} EXP** 和 **{result.stage_rewards['coins']} 金幣**！")
            self.verify.disabled = True
            await interaction.message.edit(view=self)
        else:
            lines.append("繼續加油！使用 `/stage play` 查看下一題。")

        await interaction.followup.send("\n".join(lines), ephemeral=True)


class StageCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        graph = StageGraph.load()
        leetcode_service = LeetCodeService()
        self.service = StageService(graph, leetcode_service)
        bot.tree.add_command(stage_group)

    async def _get_user_or_reply(self, interaction: discord.Interaction):
        async with AsyncSessionLocal() as session:
            user = await get_user_by_discord_id(session, interaction.user.id)
        if user is None:
            await interaction.followup.send("找不到你的帳號，請先用 `/account register` 註冊。")
        return user

    @stage_group.command(name="enroll", description="加入一個關卡")
    @app_commands.describe(stage_id="選擇要加入的關卡")
    async def enroll(self, interaction: discord.Interaction, stage_id: int):
        await interaction.response.defer()
        async with AsyncSessionLocal() as session:
            user = await get_user_by_discord_id(session, interaction.user.id)
            if user is None:
                await interaction.followup.send("找不到你的帳號，請先用 `/account register` 註冊。")
                return
            try:
                await self.service.enroll(session, user, stage_id)
            except AlreadyEnrolledError:
                await interaction.followup.send("你已經加入這個關卡了。")
                return
            except DependencyNotMetError as e:
                await interaction.followup.send(f"前置關卡未完成：{e}")
                return

        stage = self.service.graph.get_stage(stage_id)
        await interaction.followup.send(f"成功加入關卡「**{stage['name']}**」！使用 `/stage play` 開始挑戰。")

    @enroll.autocomplete("stage_id")
    async def enroll_autocomplete(self, interaction: discord.Interaction, current: str):
        async with AsyncSessionLocal() as session:
            user = await get_user_by_discord_id(session, interaction.user.id)
            if user is None:
                return []
            from backend.app.crud.stage import get_all_progress

            all_progress = await get_all_progress(session, user.id)

        completed_ids = {p.stage_id for p in all_progress if p.is_completed}
        enrolled_ids = {p.stage_id for p in all_progress}
        available = self.service.available_stages(completed_ids, enrolled_ids)

        return [app_commands.Choice(name=s["name"], value=s["id"]) for s in available if current.lower() in s["name"].lower()]

    @stage_group.command(name="list", description="列出所有關卡與解鎖狀態")
    async def list_stages(self, interaction: discord.Interaction):
        await interaction.response.defer()
        async with AsyncSessionLocal() as session:
            user = await get_user_by_discord_id(session, interaction.user.id)
            if user is None:
                await interaction.followup.send("找不到你的帳號，請先用 `/account register` 註冊。")
                return
            items = await self.service.get_list(session, user)

        embed = discord.Embed(title="關卡列表", color=discord.Color.blue())
        for item in items:
            stage = item["stage"]
            if item["completed"]:
                status = "✅ 已完成"
            elif item["enrolled"]:
                p = item["progress"]
                status = f"▶ 進行中（{p.current_problem_index}/{len(stage['problems'])}）"
            elif item["unlocked"]:
                status = "🔓 可加入"
            else:
                req_names = [self.service.graph.get_stage(r)["name"] for r in stage.get("requires", [])]
                status = f"🔒 需完成：{', '.join(req_names)}"

            rewards = stage["rewards"]
            embed.add_field(
                name=f"#{stage['id']} {stage['name']}",
                value=f"{status}\n完關獎勵：{rewards['exp']} EXP / {rewards['coins']} 金幣\n題數：{len(stage['problems'])} 題",
                inline=False,
            )

        await interaction.followup.send(embed=embed)

    @stage_group.command(name="status", description="查看你目前所有關卡的進度")
    async def status(self, interaction: discord.Interaction):
        await interaction.response.defer()
        async with AsyncSessionLocal() as session:
            user = await get_user_by_discord_id(session, interaction.user.id)
            if user is None:
                await interaction.followup.send("找不到你的帳號，請先用 `/account register` 註冊。")
                return
            all_status = await self.service.get_all_status(session, user)

        if not all_status:
            await interaction.followup.send("你還沒有加入任何關卡，使用 `/stage enroll` 開始！")
            return

        embed = discord.Embed(title="關卡進度", color=discord.Color.orange())
        for s in all_status:
            pct = int(s["done"] / s["total"] * 100)
            bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
            label = "✅ 完成" if s["is_completed"] else f"▶ {s['done']}/{s['total']} 題"
            embed.add_field(
                name=s["name"],
                value=f"{label}\n`{bar}` {pct}%",
                inline=False,
            )

        await interaction.followup.send(embed=embed)

    @stage_group.command(name="play", description="顯示目前關卡的當前題目")
    @app_commands.describe(stage_id="選擇關卡")
    async def play(self, interaction: discord.Interaction, stage_id: int):
        await interaction.response.defer()
        async with AsyncSessionLocal() as session:
            user = await get_user_by_discord_id(session, interaction.user.id)
            if user is None:
                await interaction.followup.send("找不到你的帳號，請先用 `/account register` 註冊。")
                return
            try:
                info = await self.service.get_current_problem(session, user, stage_id)
            except NotEnrolledError:
                await interaction.followup.send("你還沒加入這個關卡！使用 `/stage enroll` 加入。")
                return

        if info["is_completed"]:
            await interaction.followup.send("這個關卡已經完成了！")
            return

        problem = info["problem"]
        stage = self.service.graph.get_stage(stage_id)

        embed = discord.Embed(
            title=problem["title"],
            url=problem["url"],
            color=discord.Color.blurple(),
        )
        embed.add_field(name="平台", value=_platform_label(problem["platform"]), inline=True)
        embed.add_field(name="進度", value=f"{info['index'] + 1} / {info['total']}", inline=True)
        embed.add_field(
            name="題目獎勵",
            value=f"{problem['rewards']['exp']} EXP / {problem['rewards']['coins']} 金幣",
            inline=True,
        )
        embed.set_footer(text=f"關卡：{stage['name']}")

        view = VerifyView(stage_id=stage_id, original_user_id=interaction.user.id, service=self.service)
        await interaction.followup.send(embed=embed, view=view)

    @play.autocomplete("stage_id")
    async def play_autocomplete(self, interaction: discord.Interaction, current: str):
        async with AsyncSessionLocal() as session:
            user = await get_user_by_discord_id(session, interaction.user.id)
            if user is None:
                return []
            from backend.app.crud.stage import get_all_progress

            all_progress = await get_all_progress(session, user.id)

        enrolled = [p for p in all_progress if not p.is_completed]
        return [
            app_commands.Choice(
                name=self.service.graph.get_stage(p.stage_id)["name"],
                value=p.stage_id,
            )
            for p in enrolled
            if current.lower() in self.service.graph.get_stage(p.stage_id)["name"].lower()
        ]

    @stage_group.command(name="achievement", description="查看所有已完成的關卡紀錄")
    async def achievement(self, interaction: discord.Interaction):
        await interaction.response.defer()
        async with AsyncSessionLocal() as session:
            user = await get_user_by_discord_id(session, interaction.user.id)
            if user is None:
                await interaction.followup.send("找不到你的帳號，請先用 `/account register` 註冊。")
                return
            achievements = await self.service.get_achievements(session, user)

        if not achievements:
            await interaction.followup.send("你還沒有完成任何關卡，繼續加油！")
            return

        embed = discord.Embed(title="成就紀錄", color=discord.Color.gold())
        for a in achievements:
            started = discord.utils.format_dt(a["started_at"], style="d")
            completed = discord.utils.format_dt(a["completed_at"], style="d")
            embed.add_field(
                name=a["name"],
                value=f"開始：{started}\n完成：{completed}",
                inline=False,
            )

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(StageCog(bot))
