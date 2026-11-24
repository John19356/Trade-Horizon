import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone

from database import get_player_data, update_balance
from commands.configure import get_config
from transaction_logger import send_transaction_log
from leaderboard_engine import process_leaderboard_change


@app_commands.command(
    name="give",
    description="Give currency to a player."
)
@app_commands.describe(
    user="The player receiving the currency.",
    amount="The amount of currency to give.",
    reason="The reason for this transaction."
)
@app_commands.checks.cooldown(1, 3)
async def give_command(
    interaction: discord.Interaction,
    user: discord.Member,
    amount: app_commands.Range[int, 1, 9007199254740991],
    reason: str = "No reason provided"
):
    if interaction.guild is None:
        await interaction.response.send_message(
            "❌ This command can only be used inside a server.",
            ephemeral=True
        )
        return

    config = get_config(interaction.guild_id)

    is_server_admin = interaction.user.guild_permissions.administrator
    admin_role_id = config["admin_role"]

    has_admin_role = (
        admin_role_id is not None
        and any(
            role.id == admin_role_id
            for role in interaction.user.roles
        )
    )

    if not is_server_admin and not has_admin_role:
        await interaction.response.send_message(
            "❌ You do not have permission to use this command.",
            ephemeral=True
        )
        return

    if user.bot:
        await interaction.response.send_message(
            "❌ You cannot give currency to a bot.",
            ephemeral=True
        )
        return

    if user.id == interaction.user.id:
        await interaction.response.send_message(
            "❌ You cannot give currency to yourself.",
            ephemeral=True
        )
        return

    old_balance = get_player_data(
        interaction.guild_id,
        user.id,
        username=user.name
    )["balance"]

    new_balance = update_balance(
        interaction.guild_id,
        user.id,
        amount,
        username=user.name
    )

    await send_transaction_log(
        interaction,
        config,
        "give",
        user,
        amount,
        old_balance,
        new_balance,
        reason
    )

    await process_leaderboard_change(
        interaction.guild,
        user.id,
        amount,
        config
    )

    embed = discord.Embed(
        title="💰 Currency Given",
        description=(
            f"**{user.mention}** received "
            f"`+{amount:,} {config['currency_name']}` "
            f"{config['currency_emoji']}\n\n"
            f"**Balance:** `{old_balance:,}` → `{new_balance:,}`\n"
            f"**Reason:** {reason[:500]}"
        ),
        color=discord.Color.green(),
        timestamp=datetime.now(timezone.utc)
    )

    embed.set_footer(
        text=f"Transaction performed by {interaction.user}"
    )

    await interaction.response.send_message(embed=embed)


def setup(bot: commands.Bot):
    bot.tree.add_command(give_command)
