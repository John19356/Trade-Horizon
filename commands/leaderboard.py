
import discord

from discord import app_commands
from discord.ext import commands
from leaderboard_engine import force_refresh_leaderboard
from datetime import datetime, timezone

import re

from database import (
    load_database,
    save_database,
    ensure_server_data
)

from commands.configure import get_config

from leaderboard_engine import (
    create_leaderboard_embed,
    end_leaderboard
)


# =========================================================
# DURATION PARSER
# =========================================================

def parse_duration(duration: str):

    """
    Converts a duration string into seconds.

    Supported units:

    s  = seconds
    m  = minutes
    h  = hours
    d  = days
    w  = weeks

    Examples:

        30s
        5m
        2h
        3d
        1w

        1h 30m
        2d 6h 15m
        1d 2h 30m 45s

    Returns:
        int    -> duration in seconds
        None   -> invalid duration
    """

    if not isinstance(duration, str):
        return None

    duration = duration.strip().lower()

    if not duration:
        return None

    # -----------------------------------------------------
    # MATCH ALL TIME COMPONENTS
    # -----------------------------------------------------

    pattern = r"(\d+)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days|w|week|weeks)"

    matches = re.findall(
        pattern,
        duration
    )

    if not matches:
        return None

    # -----------------------------------------------------
    # MAKE SURE THE ENTIRE STRING WAS VALID
    # -----------------------------------------------------

    cleaned_duration = re.sub(
        pattern,
        "",
        duration
    )

    cleaned_duration = cleaned_duration.strip()

    if cleaned_duration:
        return None

    # -----------------------------------------------------
    # CONVERT TO SECONDS
    # -----------------------------------------------------

    unit_seconds = {

        # Seconds
        "s": 1,
        "sec": 1,
        "secs": 1,
        "second": 1,
        "seconds": 1,

        # Minutes
        "m": 60,
        "min": 60,
        "mins": 60,
        "minute": 60,
        "minutes": 60,

        # Hours
        "h": 3600,
        "hr": 3600,
        "hrs": 3600,
        "hour": 3600,
        "hours": 3600,

        # Days
        "d": 86400,
        "day": 86400,
        "days": 86400,

        # Weeks
        "w": 604800,
        "week": 604800,
        "weeks": 604800
    }

    total_seconds = 0

    for amount, unit in matches:

        total_seconds += (
            int(amount) * unit_seconds[unit]
        )

    # -----------------------------------------------------
    # VALIDATE RESULT
    # -----------------------------------------------------

    if total_seconds <= 0:
        return None

    return total_seconds


# =========================================================
# PERMISSION CHECK
# =========================================================

def has_leaderboard_permission(
    interaction: discord.Interaction
):

    if interaction.guild is None:
        return False

    config = get_config(
        interaction.guild_id
    )

    if not config:
        return False

    is_server_admin = (
        interaction.user.guild_permissions.administrator
    )

    admin_role_id = config.get(
        "admin_role"
    )

    has_admin_role = (
        admin_role_id is not None
        and any(
            role.id == admin_role_id
            for role in interaction.user.roles
        )
    )

    return (
        is_server_admin
        or has_admin_role
    )


# =========================================================
# /CREATE LEADERBOARD
# =========================================================

@app_commands.command(
    name="create_leaderboard",
    description="Create a timed server leaderboard."
)

@app_commands.describe(
    display_limit="How many players should be displayed?",
    leaderstat="Which statistic should be ranked?",
    duration="Duration such as 30s, 5m, 2h, 1d, 1w, or 1h 30m.",
    title="The leaderboard title.",
    subtitle="The leaderboard subtitle.",
    description="The leaderboard description.",
    color="Optional hexadecimal embed colour."
)

@app_commands.choices(
    display_limit=[
        app_commands.Choice(
            name="Top 5",
            value=5
        ),
        app_commands.Choice(
            name="Top 10",
            value=10
        )
    ],

    leaderstat=[
        app_commands.Choice(
            name="Net Earnings",
            value="balance"
        )
    ]
)

@app_commands.checks.cooldown(
    1,
    5
)

async def create_leaderboard_command(
    interaction: discord.Interaction,
    display_limit: app_commands.Choice[int],
    leaderstat: app_commands.Choice[str],
    duration: str,
    title: str,
    subtitle: str,
    description: str,
    color: str = None
):

    # =====================================================
    # SERVER VALIDATION
    # =====================================================

    if interaction.guild is None:

        await interaction.response.send_message(

            embed=discord.Embed(
                title="❌ Server Required",
                description=(
                    "This command can only be used "
                    "inside a server."
                ),
                color=discord.Color.red()
            ),

            ephemeral=True
        )

        return

    # =====================================================
    # PERMISSION CHECK
    # =====================================================

    if not has_leaderboard_permission(
        interaction
    ):

        await interaction.response.send_message(

            embed=discord.Embed(
                title="❌ Permission Denied",
                description=(
                    "You do not have permission "
                    "to create a leaderboard."
                ),
                color=discord.Color.red()
            ),

            ephemeral=True
        )

        return

    # =====================================================
    # CONFIGURATION
    # =====================================================

    config = get_config(
        interaction.guild_id
    )

    if not config:

        await interaction.response.send_message(

            embed=discord.Embed(
                title="❌ Configuration Error",
                description=(
                    "Server configuration could "
                    "not be loaded."
                ),
                color=discord.Color.red()
            ),

            ephemeral=True
        )

        return

    # =====================================================
    # DURATION VALIDATION
    # =====================================================

    duration = duration.strip().lower()

    duration_seconds = parse_duration(
        duration
    )

    if duration_seconds is None:

        await interaction.response.send_message(

            embed=discord.Embed(
                title="❌ Invalid Duration",
                description=(
                    "Invalid duration.\n\n"
                    "**Examples:**\n"
                    "`30s` • `5m` • `2h` • `1d` • `1w`\n"
                    "`1h 30m` • `2d 6h 15m`"
                ),
                color=discord.Color.red()
            ),

            ephemeral=True
        )

        return

    # =====================================================
    # TEXT VALIDATION
    # =====================================================

    title = title.strip()
    subtitle = subtitle.strip()
    description = description.strip()

    if (
        not title
        or not subtitle
        or not description
    ):

        await interaction.response.send_message(

            embed=discord.Embed(
                title="❌ Missing Fields",
                description=(
                    "Title, subtitle and description "
                    "cannot be empty."
                ),
                color=discord.Color.red()
            ),

            ephemeral=True
        )

        return

    # -----------------------------------------------------
    # TITLE
    # -----------------------------------------------------

    if len(title) > 256:

        await interaction.response.send_message(

            embed=discord.Embed(
                title="❌ Title Too Long",
                description=(
                    "Title cannot exceed "
                    "256 characters."
                ),
                color=discord.Color.red()
            ),

            ephemeral=True
        )

        return

    # -----------------------------------------------------
    # SUBTITLE
    # -----------------------------------------------------

    if len(subtitle) > 256:

        await interaction.response.send_message(

            embed=discord.Embed(
                title="❌ Subtitle Too Long",
                description=(
                    "Subtitle cannot exceed "
                    "256 characters."
                ),
                color=discord.Color.red()
            ),

            ephemeral=True
        )

        return

    # -----------------------------------------------------
    # DESCRIPTION
    # -----------------------------------------------------

    if len(description) > 3000:

        await interaction.response.send_message(

            embed=discord.Embed(
                title="❌ Description Too Long",
                description=(
                    "Description cannot exceed "
                    "3000 characters."
                ),
                color=discord.Color.red()
            ),

            ephemeral=True
        )

        return

    # =====================================================
    # COLOUR VALIDATION
    # =====================================================

    if color is None:
        color = "#90EE90"

    color = color.strip()

    if not color.startswith("#"):
        color = "#" + color

    if len(color) != 7:

        await interaction.response.send_message(

            embed=discord.Embed(
                title="❌ Invalid Colour",
                description=(
                    "Use a hexadecimal code "
                    "such as `#90EE90`."
                ),
                color=discord.Color.red()
            ),

            ephemeral=True
        )

        return

    try:

        int(
            color[1:],
            16
        )

    except ValueError:

        await interaction.response.send_message(

            embed=discord.Embed(
                title="❌ Invalid Colour",
                description=(
                    "Invalid hexadecimal "
                    "colour code."
                ),
                color=discord.Color.red()
            ),

            ephemeral=True
        )

        return

    color = color.upper()

    # =====================================================
    # DATABASE CHECK
    # =====================================================

    data = load_database()

    server_data = ensure_server_data(
        data,
        interaction.guild_id
    )

    existing_leaderboard = (
        server_data["leaderboard"]
    )

    if existing_leaderboard.get(
        "active"
    ):

        await interaction.response.send_message(

            embed=discord.Embed(
                title="❌ Active Leaderboard Exists",
                description=(
                    "This server already has "
                    "an active leaderboard.\n"
                    "Wait for it to end or use "
                    "`/end_leaderboard`."
                ),
                color=discord.Color.red()
            ),

            ephemeral=True
        )

        return

    # =====================================================
    # CREATE LEADERBOARD DATA
    # =====================================================

    ends_at = int(
        datetime.now(
            timezone.utc
        ).timestamp()
    ) + duration_seconds

    leaderboard_data = {

        "active": True,

        "settings": {

            "display_limit":
                display_limit.value,

            "leaderstat":
                leaderstat.value,

            "duration":
                duration,

            "color":
                color,

            "title":
                title,

            "subtitle":
                subtitle,

            "description":
                description
        },

        "channel_id":
            interaction.channel_id,

        "message_id":
            None,

        "ends_at":
            ends_at,

        "participants":
            {},

        "history":
            existing_leaderboard.get(
                "history",
                []
            )
    }

    # =====================================================
    # CREATE EMBED
    # =====================================================

    embed = create_leaderboard_embed(
        leaderboard_data,
        config
    )

    if interaction.guild.icon:

        embed.set_thumbnail(
            url=interaction.guild.icon.url
        )

    # =====================================================
    # DEFER RESPONSE
    # =====================================================

    await interaction.response.defer(
        ephemeral=True
    )

    # =====================================================
    # PUBLISH LEADERBOARD
    # =====================================================

    try:

        message = await interaction.channel.send(

            embed=embed,

            allowed_mentions=(
                discord.AllowedMentions.none()
            )
        )

    except discord.HTTPException as error:

        print(
            f"Leaderboard creation failed: {error}"
        )

        await interaction.followup.send(

            embed=discord.Embed(
                title="❌ Publish Failed",
                description=(
                    "I couldn't publish the leaderboard.\n"
                    "Please check my channel permissions."
                ),
                color=discord.Color.red()
            ),

            ephemeral=True
        )

        return

    # =====================================================
    # SAVE LEADERBOARD
    # =====================================================

    leaderboard_data[
        "message_id"
    ] = message.id

    server_data[
        "leaderboard"
    ] = leaderboard_data

    save_database(data)

    # =====================================================
    # CONFIRMATION
    # =====================================================

    confirm_embed = discord.Embed(

        title="✅ Leaderboard Published",

        description=(
            f"Your leaderboard **{title}** "
            f"is now live in "
            f"{interaction.channel.mention}."
        ),

        color=discord.Color(
            int(color[1:], 16)
        )
    )

    confirm_embed.add_field(

        name="📊 Display",

        value=(
            f"Top {display_limit.value}"
        ),

        inline=True
    )

    confirm_embed.add_field(

        name="⏳ Ends",

        value=f"<t:{ends_at}:R>",

        inline=True
    )

    confirm_embed.add_field(

        name="⏱️ Duration",

        value=f"`{duration}`",

        inline=True
    )

    confirm_embed.set_footer(
        text="Trade Horizon™ Leaderboard Service"
    )

    await interaction.followup.send(
        embed=confirm_embed,
        ephemeral=True
    )


# =========================================================
# /END LEADERBOARD
# =========================================================

@app_commands.command(
    name="end_leaderboard",
    description="Manually end the active server leaderboard."
)

@app_commands.checks.cooldown(
    1,
    5
)

async def end_leaderboard_command(
    interaction: discord.Interaction
):

    # =====================================================
    # SERVER VALIDATION
    # =====================================================

    if interaction.guild is None:

        await interaction.response.send_message(

            embed=discord.Embed(
                title="❌ Server Required",
                description=(
                    "This command can only be used "
                    "inside a server."
                ),
                color=discord.Color.red()
            ),

            ephemeral=True
        )

        return

    # =====================================================
    # PERMISSION CHECK
    # =====================================================

    if not has_leaderboard_permission(
        interaction
    ):

        await interaction.response.send_message(

            embed=discord.Embed(
                title="❌ Permission Denied",
                description=(
                    "You do not have permission "
                    "to end the leaderboard."
                ),
                color=discord.Color.red()
            ),

            ephemeral=True
        )

        return

    # =====================================================
    # CHECK ACTIVE LEADERBOARD
    # =====================================================

    data = load_database()

    server_data = ensure_server_data(
        data,
        interaction.guild_id
    )

    if not server_data[
        "leaderboard"
    ].get("active"):

        await interaction.response.send_message(

            embed=discord.Embed(
                title="❌ No Active Leaderboard",
                description=(
                    "There is no active leaderboard "
                    "to end."
                ),
                color=discord.Color.red()
            ),

            ephemeral=True
        )

        return

    # =====================================================
    # DEFER RESPONSE
    # =====================================================

    await interaction.response.defer(
        ephemeral=True
    )

    # =====================================================
    # END LEADERBOARD
    # =====================================================

    try:

        success = await end_leaderboard(
            interaction.guild,
            reason="manual"
        )

    except Exception as error:

        print(
            f"Manual leaderboard ending failed: {error}"
        )

        await interaction.followup.send(

            embed=discord.Embed(
                title="❌ Error Ending Leaderboard",
                description=(
                    "An error occurred while "
                    "ending the leaderboard."
                ),
                color=discord.Color.red()
            ),

            ephemeral=True
        )

        return

    # =====================================================
    # CONFIRMATION
    # =====================================================

    if success:

        ended_embed = discord.Embed(

            title="🏆 Leaderboard Ended",

            description=(
                "The leaderboard has ended successfully "
                "and final results have been announced."
            ),

            color=discord.Color.gold()
        )

        ended_embed.set_footer(
            text="Trade Horizon™ Leaderboard Service"
        )

        await interaction.followup.send(
            embed=ended_embed,
            ephemeral=True
        )

    else:

        await interaction.followup.send(

            embed=discord.Embed(
                title="❌ Already Ended",
                description=(
                    "The leaderboard is no longer active."
                ),
                color=discord.Color.red()
            ),

            ephemeral=True
        )



# =========================================================
# SETUP
# =========================================================

def setup(bot: commands.Bot):
    @bot.tree.command(
        name="update",
        description="Refresh and apply changes to the active leaderboard message."
    )
    async def update_cmd(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        ok, message = await force_refresh_leaderboard(interaction.guild)

        if ok:
            await interaction.followup.send(f"✅ {message}", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ {message}", ephemeral=True)

    bot.tree.add_command(
        create_leaderboard_command
    )

    bot.tree.add_command(
        end_leaderboard_command
    )
