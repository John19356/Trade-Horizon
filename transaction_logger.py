import discord
from datetime import datetime, timezone


async def send_transaction_log(
    interaction,
    config,
    action,
    user,
    amount,
    old_balance,
    new_balance,
    reason
):
    channel_id = config.get("log_channel")

    if not channel_id or interaction.guild is None:
        return

    channel = interaction.guild.get_channel(channel_id)

    if channel is None:
        try:
            channel = await interaction.guild.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return

    is_give = action == "give"
    currency_name = config.get("currency_name", "Coins")
    currency_emoji = config.get("currency_emoji", "🪙")

    embed = discord.Embed(
        title=(
            "💰 Currency Given"
            if is_give
            else "💸 Currency Subtracted"
        ),
        description=(
            f"**{user.mention}** "
            f"{'received' if is_give else 'lost'} "
            f"`{'+' if is_give else '-'}{amount:,} "
            f"{currency_name}` "
            f"{currency_emoji}\n\n"
            f"**Staff:** {interaction.user.mention}\n"
            f"**Balance:** `{old_balance:,}` → `{new_balance:,}`\n"
            f"**Reason:** {reason[:500]}"
        ),
        color=(
            discord.Color.green()
            if is_give
            else discord.Color.red()
        ),
        timestamp=datetime.now(timezone.utc)
    )

    embed.set_footer(
        text="Trade Horizon™ Transaction Logs"
    )

    try:
        await channel.send(
            embed=embed,
            allowed_mentions=discord.AllowedMentions.none()
        )
    except discord.HTTPException as error:
        print(f"Transaction log delivery failed: {error}")