import asyncio
import os
from pathlib import Path

import discord
from discord.ext import commands

from bot.config import settings


class Color:
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    RESET = "\033[0m"


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="@", intents=intents)


@bot.event
async def on_ready():
    print(f"{bot.user.name} login...: OK!")


@bot.event
async def setup_hook():
    print(f"{Color.CYAN}[System] Starting automatic module scan and loading...{Color.RESET}")

    cogs_dir = Path(__file__).parent / "cogs"

    for filepath in cogs_dir.rglob("*.py"):
        if filepath.name == "__init__.py":
            continue

        project_root = Path(__file__).parent.parent
        relative_path = filepath.relative_to(project_root)
        module_name = str(relative_path).replace(os.path.sep, ".").removesuffix(".py")

        try:
            await bot.load_extension(module_name)
            print(f"[{Color.GREEN} OK {Color.RESET}] Loaded module: {Color.PURPLE}{filepath.stem}{Color.RESET}")
        except Exception as e:
            print(f"[{Color.RED}FAILED{Color.RESET}] Module {Color.YELLOW}{filepath.stem}{Color.RESET} failed to load!")
            print(f"       └─ Reason: {Color.RED}{str(e)}{Color.RESET}")

    print(f"{Color.GREEN}All modules loaded dynamically, bot is ready!{Color.RESET}")

    synced = await bot.tree.sync()
    print(f"{Color.GREEN}[System] Synced {len(synced)} slash command(s).{Color.RESET}")


async def main():
    async with bot:
        await bot.start(settings.discord_token)


if __name__ == "__main__":
    asyncio.run(main())
