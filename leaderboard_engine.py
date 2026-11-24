import discord

from datetime import datetime, timezone
import re

from database import (
    load_database,
    save_database,
    ensure_server_data
)


def get_ranked_players(leaderboard_data):
    participants = leaderboard_data.get(
        "participants",
        {}
    )

    filtered_players = [
        (user_id, score)
        for user_id, score in participants.items()
        if score > 0
    ]

    ranked_players = sorted(
        filtered_players,
        key=lambda item: item[1],
        reverse=True
    )

    return ranked_players

    return ranked_players


def update_competition_score(
    leaderboard_data,
    user_id,
    amount
):
    if not leaderboard_data.get("active"):
        return False

    participants = leaderboard_data.setdefault(
        "participants",
        {}
    )

    user_id = str(user_id)

    current_score = participants.get(
        user_id,
        0
    )

    participants[user_id] = (
        current_score + amount
    )

    return True


def get_embed_color(color_hex):
    try:
        return discord.Color(
            int(
                color_hex.replace("#", ""),
                16
            )
        )
    except (
        ValueError,
        AttributeError
    ):
        return discord.Color.green()


def clean_display_text(text):
    if not text:
        return ""

    cleaned = re.sub(
        r"[🏆⚡⏳✅🎯📊⏱️💰📈🗓️🏁🏅]",
        "",
        str(text)
    )

    cleaned = re.sub(
        r"\s+",
        " ",
        cleaned
    ).strip()

    return cleaned


def resolve_player_label(
    players,
    user_id
):
    uid_str = str(user_id)

    player_data = players.get(
        uid_str
    )

    if isinstance(
        player_data,
        dict
    ):
        username = player_data.get(
            "username"
        )

        if username:
            return str(
                username
            )[:14]

    return f"u_{uid_str[-4:]}"


def get_duration_days(duration):
    if not duration:
        return None

    duration = str(
        duration
    ).strip().lower()

    matches = re.findall(
        r"(\d+(?:\.\d+)?)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)",
        duration
    )

    if not matches:
        return None

    total_seconds = 0

    unit_multipliers = {
        "s": 1,
        "sec": 1,
        "secs": 1,
        "second": 1,
        "seconds": 1,
        "m": 60,
        "min": 60,
        "mins": 60,
        "minute": 60,
        "minutes": 60,
        "h": 3600,
        "hr": 3600,
        "hrs": 3600,
        "hour": 3600,
        "hours": 3600,
        "d": 86400,
        "day": 86400,
        "days": 86400
    }

    for amount, unit in matches:
        total_seconds += (
            float(amount) * unit_multipliers[unit]
        )

    if total_seconds <= 0:
        return None

    return (
        total_seconds / 86400
    )


def get_total_score(
    leaderboard_data
):
    participants = leaderboard_data.get(
        "participants",
        {}
    )

    return sum(
        participants.values()
    )


def get_average_per_day(
    leaderboard_data
):
    total_score = get_total_score(
        leaderboard_data
    )

    settings = leaderboard_data.get(
        "settings",
        {}
    )

    duration = settings.get(
        "duration"
    )

    duration_days = get_duration_days(
        duration
    )

    if not duration_days:
        return None

    return (
        total_score / duration_days
    )


def create_leaderboard_embed(
    leaderboard_data,
    config,
    guild=None
):
    settings = leaderboard_data.get(
        "settings",
        {}
    )

    raw_title = (
        settings.get("title")
        or "Leaderboard"
    )

    subtitle = clean_display_text(
        settings.get("subtitle")
        or ""
    )

    description = clean_display_text(
        settings.get("description")
        or ""
    )

    display_limit = (
        settings.get("display_limit")
    )

    color_hex = (
        settings.get(
            "color",
            "#90EE90"
        )
    )

    embed_color = get_embed_color(
        color_hex
    )

    currency_name = config.get(
        "currency_name",
        "Coins"
    )

    currency_emoji = config.get(
        "currency_emoji",
        "🪙"
    )

    players = {}

    if guild is not None:
        try:
            data = load_database()

            server_data = data.get(
                str(guild.id),
                {}
            )

            players = server_data.get(
                "players",
                {}
            )
        except Exception as error:
            print(
                "Failed to load player data: "
                f"{error}"
            )

    clean_title = (
        clean_display_text(
            raw_title
        )
        or "Leaderboard"
    )

    desc_parts = []

    if subtitle:
        desc_parts.append(
            f"**{subtitle}**"
        )

    if description:
        desc_parts.append(
            description
        )

    embed = discord.Embed(
        title=(
            f"⚡ {clean_title.upper()}"
        ),
        description=(
            "\n\n".join(desc_parts)
            if desc_parts
            else None
        ),
        color=embed_color
    )

    board_label = (
        f"Top {display_limit}"
        if display_limit
        else "All"
    )

    duration = settings.get(
        "duration"
    )

    ends_at = leaderboard_data.get(
        "ends_at"
    )

    info_lines = [
        f"**Board:** `{board_label}`"
    ]

    if duration:
        info_lines.append(
            f"**Window:** `{duration}`"
        )

    if ends_at:
        info_lines.append(
            f"**Ends:** <t:{int(ends_at)}:R>"
        )

    embed.add_field(
        name="📌 Overview",
        value="\n".join(
            info_lines
        ),
        inline=False
    )

    ranked_players = get_ranked_players(
        leaderboard_data
    )

    if display_limit:
        ranked_players = (
            ranked_players[
                :int(display_limit)
            ]
        )

    if not ranked_players:
        embed.add_field(
            name=f"Standing [{currency_name}]",
            value=(
                "No contenders yet.\n"
                "Claim #1 on the board."
            ),
            inline=False
        )
    else:
        ranking_lines = []

        medals = {
            1: "🥇",
            2: "🥈",
            3: "🥉"
        }

        for position, (
            user_id,
            score
        ) in enumerate(
            ranked_players,
            start=1
        ):
            prefix = medals.get(
                position,
                f"#{position}"
            )

            player_name = (
                resolve_player_label(
                    players,
                    user_id
                )
            )

            ranking_lines.append(
                f"> {prefix} "
                f"`{player_name}` - "
                f"`{score:,}`"
            )

        standings_text = "\n".join(
            ranking_lines
        )

        embed.add_field(
            name=f"🏆 Standing [{currency_name}] {currency_emoji}",
            value=standings_text,
            inline=False
        )

    total_score = get_total_score(
        leaderboard_data
    )

    average_per_day = (
        get_average_per_day(
            leaderboard_data
        )
    )

    if average_per_day is not None:
        avg_text = (
            f"`{average_per_day:,.1f}/day`"
        )
    else:
        avg_text = "`N/A`"

    embed.add_field(
        name="💰 Stats",
        value=(
            f"**Total:** "
            f"`{total_score:,} {currency_name}` "
            f"{currency_emoji}\n\n"
            f"**Average:** "
            f"{avg_text}"
        ),
        inline=False
    )

    if ends_at:
        embed.add_field(
            name="🗓️ Deadline",
            value=(
                f"<t:{int(ends_at)}:f>"
            ),
            inline=False
        )

    embed.set_footer(
        text=(
            "Trade Horizon™ • "
            "Leaderboard Service"
        )
    )

    return embed


async def refresh_leaderboard(
    guild,
    leaderboard_data,
    config
):
    channel_id = (
        leaderboard_data.get(
            "channel_id"
        )
    )

    message_id = (
        leaderboard_data.get(
            "message_id"
        )
    )

    if (
        not channel_id
        or not message_id
    ):
        return

    channel = guild.get_channel(
        channel_id
    )

    if channel is None:
        try:
            channel = await guild.fetch_channel(
                channel_id
            )
        except (
            discord.NotFound,
            discord.Forbidden
        ):
            return
        except discord.HTTPException as error:
            print(
                "Leaderboard channel "
                f"fetch failed: {error}"
            )
            return

    try:
        message = await channel.fetch_message(
            message_id
        )

        embed = create_leaderboard_embed(
            leaderboard_data,
            config,
            guild=guild
        )

        if guild.icon:
            embed.set_thumbnail(
                url=guild.icon.url
            )

        await message.edit(
            embed=embed,
            allowed_mentions=(
                discord.AllowedMentions.none()
            )
        )

    except discord.NotFound:
        print(
            "Leaderboard message "
            "was not found."
        )
    except discord.Forbidden:
        print(
            "Missing permission to "
            "edit leaderboard message."
        )
    except discord.HTTPException as error:
        print(
            "Leaderboard refresh "
            f"failed: {error}"
        )


async def force_refresh_leaderboard(guild):
    if guild is None:
        return False, "This command can only be used inside a server."

    data = load_database()
    server_data = ensure_server_data(data, str(guild.id))
    save_database(data)

    leaderboard_data = server_data.get("leaderboard", {})

    if not leaderboard_data.get("active"):
        return False, "There is no active leaderboard to update."

    config = server_data.get("config", {})
    await refresh_leaderboard(guild, leaderboard_data, config)
    return True, "Leaderboard updated to the latest settings and standings."


async def process_leaderboard_change(
    guild,
    user_id,
    amount,
    config
):
    data = load_database()

    ensure_server_data(
        data,
        str(guild.id)
    )

    server_data = data[
        str(guild.id)
    ]

    leaderboard_data = (
        server_data.get(
            "leaderboard",
            {}
        )
    )

    if not leaderboard_data.get(
        "active"
    ):
        return

    settings = (
        leaderboard_data.get(
            "settings",
            {}
        )
    )

    if settings.get(
        "leaderstat"
    ) != "balance":
        return

    updated = update_competition_score(
        leaderboard_data,
        str(user_id),
        amount
    )

    if not updated:
        return

    save_database(data)

    await refresh_leaderboard(
        guild,
        leaderboard_data,
        config
    )


async def end_leaderboard(
    guild,
    reason="manual"
):
    data = load_database()

    ensure_server_data(
        data,
        str(guild.id)
    )

    server_data = data[
        str(guild.id)
    ]

    leaderboard_data = (
        server_data.get(
            "leaderboard",
            {}
        )
    )

    if not leaderboard_data.get(
        "active"
    ):
        return False

    config = server_data.get(
        "config",
        {}
    )

    ended_timestamp = int(
        datetime.now(
            timezone.utc
        ).timestamp()
    )

    channel_id = (
        leaderboard_data.get(
            "channel_id"
        )
    )

    message_id = (
        leaderboard_data.get(
            "message_id"
        )
    )

    final_participants = (
        leaderboard_data.get(
            "participants",
            {}
        ).copy()
    )

    ended_leaderboard_data = {
        **leaderboard_data,
        "participants":
            final_participants,
        "ends_at":
            None
    }

    ranked_players = (
        get_ranked_players(
            ended_leaderboard_data
        )
    )

    settings = (
        leaderboard_data.get(
            "settings",
            {}
        )
    )

    history_entry = {
        "title":
            settings.get(
                "title"
            ),
        "subtitle":
            settings.get(
                "subtitle"
            ),
        "description":
            settings.get(
                "description"
            ),
        "duration":
            settings.get(
                "duration"
            ),
        "started_at":
            leaderboard_data.get(
                "started_at"
            ),
        "ended_at":
            ended_timestamp,
        "reason":
            reason,
        "participants":
            final_participants,
        "rankings": [
            {
                "user_id":
                    str(user_id),
                "score":
                    score
            }
            for user_id, score
            in ranked_players
        ]
    }

    history = (
        leaderboard_data.setdefault(
            "history",
            []
        )
    )

    history.append(
        history_entry
    )

    leaderboard_data[
        "active"
    ] = False

    leaderboard_data[
        "channel_id"
    ] = None

    leaderboard_data[
        "message_id"
    ] = None

    leaderboard_data[
        "ends_at"
    ] = None

    leaderboard_data[
        "participants"
    ] = {}

    save_database(data)

    if (
        channel_id
        and message_id
    ):
        channel = guild.get_channel(
            channel_id
        )

        if channel is None:
            try:
                channel = await guild.fetch_channel(
                    channel_id
                )
            except (
                discord.NotFound,
                discord.Forbidden
            ):
                channel = None
            except discord.HTTPException as error:
                print(
                    "Leaderboard channel "
                    f"fetch failed: {error}"
                )
                channel = None

        if channel is not None:
            try:
                message = await channel.fetch_message(
                    message_id
                )

                ended_embed = create_leaderboard_embed(
                    ended_leaderboard_data,
                    config,
                    guild=guild
                )

                if guild.icon:
                    ended_embed.set_thumbnail(
                        url=guild.icon.url
                    )

                ended_embed.add_field(
                    name="🏁 Status",
                    value=(
                        f"Ended <t:{ended_timestamp}:R>\n\n"
                        f"<t:{ended_timestamp}:f>"
                    ),
                    inline=False
                )

                await message.edit(
                    embed=ended_embed,
                    allowed_mentions=(
                        discord.AllowedMentions.none()
                    )
                )

            except discord.NotFound:
                print(
                    "Original leaderboard "
                    "message was not found."
                )
            except discord.Forbidden:
                print(
                    "Missing permission to "
                    "edit original leaderboard."
                )
            except discord.HTTPException as error:
                print(
                    "Ended leaderboard "
                    f"update failed: {error}"
                )

    if channel_id:
        announcement_channel = (
            guild.get_channel(
                channel_id
            )
        )

        if announcement_channel is None:
            try:
                announcement_channel = (
                    await guild.fetch_channel(
                        channel_id
                    )
                )
            except (
                discord.NotFound,
                discord.Forbidden
            ):
                announcement_channel = None
            except discord.HTTPException as error:
                print(
                    "Announcement channel "
                    f"fetch failed: {error}"
                )
                announcement_channel = None

        if announcement_channel is not None:
            color_hex = (
                settings.get(
                    "color",
                    "#90EE90"
                )
            )

            announcement_color = (
                get_embed_color(
                    color_hex
                )
            )

            board_title = (
                clean_display_text(
                    settings.get(
                        "title",
                        "Leaderboard"
                    )
                )
                or "Leaderboard"
            )

            winner_embed = discord.Embed(
                title=(
                    f"🏆 "
                    f"{board_title.upper()} "
                    f"FINAL RESULTS"
                ),
                description=(
                    "The competition has wrapped up.\n\n"
                    "Top finishers:"
                ),
                color=announcement_color
            )

            players = {}

            try:
                current_data = load_database()

                current_server_data = (
                    current_data.get(
                        str(guild.id),
                        {}
                    )
                )

                players = (
                    current_server_data.get(
                        "players",
                        {}
                    )
                )
            except Exception as error:
                print(
                    "Failed to load player data: "
                    f"{error}"
                )

            medals = {
                1: "🥇",
                2: "🥈",
                3: "🥉"
            }

            currency_name = (
                config.get(
                    "currency_name",
                    "Coins"
                )
            )

            currency_emoji = (
                config.get(
                    "currency_emoji",
                    "🪙"
                )
            )

            if ranked_players:
                top_three = (
                    ranked_players[:3]
                )

                podium_lines = []

                for position, (
                    user_id,
                    score
                ) in enumerate(
                    top_three,
                    start=1
                ):
                    player_name = (
                        resolve_player_label(
                            players,
                            user_id
                        )
                    )

                    podium_lines.append(
                        f"> {medals[position]} "
                        f"`{player_name}` - "
                        f"`{score:,} {currency_name}` "
                        f"{currency_emoji}"
                    )

                podium_text = "\n".join(
                    podium_lines
                )

                winner_embed.add_field(
                    name="🏅 Podium",
                    value=podium_text,
                    inline=False
                )
            else:
                winner_embed.add_field(
                    name="📊 Results",
                    value=(
                        "No participants joined."
                    ),
                    inline=False
                )

            winner_embed.add_field(
                name="🏁 Ended",
                value=(
                    f"<t:{ended_timestamp}:R>\n\n"
                    f"<t:{ended_timestamp}:f>"
                ),
                inline=False
            )

            winner_embed.set_footer(
                text=(
                    "Trade Horizon™ • "
                    "Leaderboard Service"
                )
            )

            if guild.icon:
                winner_embed.set_thumbnail(
                    url=guild.icon.url
                )

            try:
                await announcement_channel.send(
                    embed=winner_embed,
                    allowed_mentions=(
                        discord.AllowedMentions.none()
                    )
                )
            except discord.Forbidden:
                print(
                    "Missing permission to "
                    "send winner announcement."
                )
            except discord.HTTPException as error:
                print(
                    "Winner announcement "
                    f"failed: {error}"
                )

    return True


async def check_expired_leaderboards(
    bot
):
    current_timestamp = int(
        datetime.now(
            timezone.utc
        ).timestamp()
    )

    data = load_database()

    for guild in bot.guilds:
        guild_id = str(
            guild.id
        )

        ensure_server_data(
            data,
            guild_id
        )

        server_data = data[
            guild_id
        ]

        leaderboard_data = (
            server_data.get(
                "leaderboard",
                {}
            )
        )

        if not leaderboard_data.get(
            "active"
        ):
            continue

        ends_at = (
            leaderboard_data.get(
                "ends_at"
            )
        )

        if not ends_at:
            continue

        if current_timestamp >= int(
            ends_at
        ):
            print(
                "Leaderboard expired in "
                f"server: {guild.name}"
            )

            try:
                await end_leaderboard(
                    guild,
                    reason="timer"
                )
            except Exception as error:
                print(
                    "Failed to end leaderboard "
                    f"in {guild.name}: {error}"
                )