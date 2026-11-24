import os
import asyncio
import discord

from discord import app_commands
from discord.ext import commands, tasks

from leaderboard_engine import check_expired_leaderboards
from dotenv import load_dotenv

from commands import configure, give, subtract, leaderboard


load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing from the .env file.")


intents = discord.Intents.default()
intents.members = False

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

synced_once = False


configure.setup(bot)
give.setup(bot)
subtract.setup(bot)
leaderboard.setup(bot)


@tasks.loop(seconds=5)
async def leaderboard_expiration_loop():
    await check_expired_leaderboards(bot)


@leaderboard_expiration_loop.before_loop
async def before_leaderboard_expiration():
    await bot.wait_until_ready()


@bot.tree.interaction_check
async def log_application_command(interaction: discord.Interaction):
    if interaction.command:
        print("----------------------------------------")
        print(f"COMMAND: /{interaction.command.qualified_name}")
        print(f"USER: {interaction.user}")
        print(
            f"SERVER: {interaction.guild.name}"
            if interaction.guild
            else "SERVER: DM"
        )
        print("STATUS: Executing...")
        print("----------------------------------------")

    return True


@bot.event
async def on_ready():
    global synced_once

    print("----------------------------------------")
    print(f"Logged in as: {bot.user}")
    print(f"Bot ID: {bot.user.id}")

    if not synced_once:
        try:
            synced = await bot.tree.sync()
            synced_once = True

            print(
                f"Synced {len(synced)} application command(s)."
            )

            for command in synced:
                print(f"  /{command.name}")

        except Exception as error:
            print(f"Command sync failed: {error}")

    if not leaderboard_expiration_loop.is_running():
        leaderboard_expiration_loop.start()
        print("Leaderboard expiration system started.")

    print("Trade Horizon™ is online!")
    print("----------------------------------------")


@bot.tree.command(
    name="ping",
    description="Check if the bot is online."
)
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(
        "🏓 Pong!"
    )


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError
):
    print("----------------------------------------")
    print("APPLICATION COMMAND ERROR:")
    print(repr(error))

    if isinstance(error, app_commands.CommandInvokeError):
        print(
            "Original error:",
            repr(error.original)
        )

    print("----------------------------------------")

    message = (
        "❌ An error occurred while executing this command."
    )

    try:
        if interaction.response.is_done():
            await interaction.followup.send(
                message,
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                message,
                ephemeral=True
            )

    except discord.HTTPException as send_error:
        print(
            "Could not send error response:",
            repr(send_error)
        )


async def main():
    async with bot:
        await bot.start(TOKEN)

TEST_GUILD_ID = 1517951657953071255  # Replace with your test server ID


@bot.event
async def on_ready():
    global synced_once

    print("----------------------------------------")
    print(f"Logged in as: {bot.user}")
    print(f"Bot ID: {bot.user.id}")

    if not synced_once:
        try:
            test_guild = discord.Object(id=TEST_GUILD_ID)
            bot.tree.copy_global_to(guild=test_guild)
            synced = await bot.tree.sync(guild=test_guild)
            synced_once = True

            print(
                f"Synced {len(synced)} command(s) to test guild {TEST_GUILD_ID}."
            )
            for command in synced:
                print(f"  /{command.name}")
        except Exception as error:
            print(f"Command sync failed: {error}")

    if not leaderboard_expiration_loop.is_running():
        leaderboard_expiration_loop.start()
        print("Leaderboard expiration system started.")

    print("Trade Horizon™ is online!")
    print("----------------------------------------")


if __name__ == "__main__":
    asyncio.run(main())