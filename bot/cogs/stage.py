import discord
from discord import app_commands
from discord.ext import commands

from backend.app.core.config import settings
from backend.app.core.db import AsyncSessionLocal
from backend.app.crud import stage_def as stage_def_crud
from backend.app.crud.user import get_user_by_discord_id
from backend.app.services.leetcode.client import LeetCodeService
from backend.app.services.stage.service import (
    AlreadyEnrolledError,
    DependencyNotMetError,
    NoLeetCodeAccountError,
    NotEnrolledError,
    StageService,
)

stage_group = app_commands.Group(name="stage", description="關卡挑戰系統")
admin_group = app_commands.Group(name="admin", description="關卡管理（限管理員）", parent=stage_group)


def _is_admin(discord_id: int) -> bool:
    return discord_id in settings.admin_discord_ids


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

        lines = [f"獲得 **{result.problem_rewards['exp']} EXP** 和 **{result.problem_rewards['coins']} 金幣**！"]

        if result.stage_complete:
            lines.append(
                f"🎉 關卡完成！額外獲得 **{result.stage_rewards['exp']} EXP** 和 **{result.stage_rewards['coins']} 金幣**！"
            )
            self.verify.disabled = True
            await interaction.message.edit(view=self)
        else:
            lines.append("繼續加油！使用 `/stage play` 查看下一題。")

        await interaction.followup.send("\n".join(lines), ephemeral=True)


class StageCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.service = StageService(LeetCodeService())

    # ── User commands ──────────────────────────────────────────────────────

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
                stage = await self.service.get_stage(session, stage_id)
            except AlreadyEnrolledError:
                await interaction.followup.send("你已經加入這個關卡了。")
                return
            except DependencyNotMetError as e:
                await interaction.followup.send(f"前置關卡未完成：{e}")
                return

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
            available = await self.service.available_stages(session, completed_ids, enrolled_ids)

        return [
            app_commands.Choice(name=s["name"], value=s["id"])
            for s in available
            if current.lower() in s["name"].lower()
        ]

    @stage_group.command(name="list", description="列出所有關卡與解鎖狀態")
    async def list_stages(self, interaction: discord.Interaction):
        await interaction.response.defer()
        async with AsyncSessionLocal() as session:
            user = await get_user_by_discord_id(session, interaction.user.id)
            if user is None:
                await interaction.followup.send("找不到你的帳號，請先用 `/account register` 註冊。")
                return
            items = await self.service.get_list(session, user)

        if not items:
            await interaction.followup.send("目前還沒有任何關卡，請等待管理員新增！")
            return

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
                req_names = [
                    items[i]["stage"]["name"]
                    for i, it in enumerate(items)
                    if it["stage"]["id"] in stage.get("requires", [])
                ]
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
            pct = int(s["done"] / s["total"] * 100) if s["total"] else 0
            bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
            label = "✅ 完成" if s["is_completed"] else f"▶ {s['done']}/{s['total']} 題"
            embed.add_field(name=s["name"], value=f"{label}\n`{bar}` {pct}%", inline=False)

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
                stage = await self.service.get_stage(session, stage_id)
            except NotEnrolledError:
                await interaction.followup.send("你還沒加入這個關卡！使用 `/stage enroll` 加入。")
                return

        if info["is_completed"]:
            await interaction.followup.send("這個關卡已經完成了！")
            return

        problem = info["problem"]
        embed = discord.Embed(title=problem["title"], url=problem["url"], color=discord.Color.blurple())
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
            stages = {s["id"]: s for s in await self.service.get_all_stages(session)}

        return [
            app_commands.Choice(name=stages[p.stage_id]["name"], value=p.stage_id)
            for p in enrolled
            if p.stage_id in stages and current.lower() in stages[p.stage_id]["name"].lower()
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
            embed.add_field(name=a["name"], value=f"開始：{started}\n完成：{completed}", inline=False)

        await interaction.followup.send(embed=embed)

    # ── Admin commands ─────────────────────────────────────────────────────

    @admin_group.command(name="create", description="新增關卡")
    @app_commands.describe(name="關卡名稱", rewards_exp="完關 EXP 獎勵", rewards_coins="完關金幣獎勵")
    async def admin_create(
        self, interaction: discord.Interaction, name: str, rewards_exp: int, rewards_coins: int
    ):
        if not _is_admin(interaction.user.id):
            await interaction.response.send_message("你沒有權限執行此指令。", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        async with AsyncSessionLocal() as session:
            stage = await stage_def_crud.create_stage(session, name, rewards_exp, rewards_coins)
        await interaction.followup.send(f"關卡「**{stage.name}**」建立成功（ID: `{stage.id}`）。", ephemeral=True)

    @admin_group.command(name="delete", description="刪除關卡")
    @app_commands.describe(stage_id="要刪除的關卡 ID")
    async def admin_delete(self, interaction: discord.Interaction, stage_id: int):
        if not _is_admin(interaction.user.id):
            await interaction.response.send_message("你沒有權限執行此指令。", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        async with AsyncSessionLocal() as session:
            deleted = await stage_def_crud.delete_stage(session, stage_id)
        if not deleted:
            await interaction.followup.send(f"找不到 ID 為 `{stage_id}` 的關卡。", ephemeral=True)
        else:
            await interaction.followup.send(f"關卡 `{stage_id}` 已刪除。", ephemeral=True)

    @admin_group.command(name="requires", description="設定關卡的前置依賴")
    @app_commands.describe(stage_id="關卡 ID", required_ids="前置關卡 ID，以逗號分隔（留空代表無依賴）")
    async def admin_requires(
        self, interaction: discord.Interaction, stage_id: int, required_ids: str = ""
    ):
        if not _is_admin(interaction.user.id):
            await interaction.response.send_message("你沒有權限執行此指令。", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        requires = [int(x.strip()) for x in required_ids.split(",") if x.strip()]
        async with AsyncSessionLocal() as session:
            try:
                stage = await stage_def_crud.set_requires(session, stage_id, requires)
                # validate no cycles
                all_stages = await self.service.get_all_stages(session)
                from backend.app.services.stage.graph import CyclicDependencyError, StageGraph

                StageGraph(all_stages)
            except stage_def_crud.StageNotFoundError:
                await interaction.followup.send(f"找不到 ID 為 `{stage_id}` 的關卡。", ephemeral=True)
                return
            except CyclicDependencyError as e:
                await stage_def_crud.set_requires(session, stage_id, [])
                await interaction.followup.send(f"設定失敗（形成循環依賴）：{e}", ephemeral=True)
                return
        await interaction.followup.send(
            f"關卡 `{stage.name}` 的前置依賴已更新為：`{requires or '無'}`", ephemeral=True
        )

    @admin_group.command(name="add-problem", description="在關卡末尾新增一題")
    @app_commands.describe(
        stage_id="關卡 ID",
        url="題目連結",
        title="題目名稱",
        platform="平台（leetcode / atcoder / codeforces）",
        rewards_exp="解題 EXP 獎勵",
        rewards_coins="解題金幣獎勵",
    )
    async def admin_add_problem(
        self,
        interaction: discord.Interaction,
        stage_id: int,
        url: str,
        title: str,
        platform: str,
        rewards_exp: int,
        rewards_coins: int,
    ):
        if not _is_admin(interaction.user.id):
            await interaction.response.send_message("你沒有權限執行此指令。", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        problem = {"url": url, "title": title, "platform": platform, "rewards": {"exp": rewards_exp, "coins": rewards_coins}}
        async with AsyncSessionLocal() as session:
            try:
                stage = await stage_def_crud.add_problem(session, stage_id, problem)
            except stage_def_crud.StageNotFoundError:
                await interaction.followup.send(f"找不到 ID 為 `{stage_id}` 的關卡。", ephemeral=True)
                return
        await interaction.followup.send(
            f"題目「**{title}**」已加入關卡「{stage.name}」（目前共 {len(stage.problems)} 題）。", ephemeral=True
        )

    @admin_group.command(name="remove-problem", description="移除關卡中的某題（依編號，從 0 開始）")
    @app_commands.describe(stage_id="關卡 ID", problem_index="題目編號（0-indexed）")
    async def admin_remove_problem(self, interaction: discord.Interaction, stage_id: int, problem_index: int):
        if not _is_admin(interaction.user.id):
            await interaction.response.send_message("你沒有權限執行此指令。", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        async with AsyncSessionLocal() as session:
            try:
                stage = await stage_def_crud.remove_problem(session, stage_id, problem_index)
            except stage_def_crud.StageNotFoundError:
                await interaction.followup.send(f"找不到 ID 為 `{stage_id}` 的關卡。", ephemeral=True)
                return
            except stage_def_crud.ProblemIndexError as e:
                await interaction.followup.send(str(e), ephemeral=True)
                return
        await interaction.followup.send(
            f"已移除第 `{problem_index}` 題，關卡「{stage.name}」目前剩 {len(stage.problems)} 題。", ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(StageCog(bot))
