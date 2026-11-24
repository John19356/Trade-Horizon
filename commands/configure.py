
import discord
from discord import app_commands
from discord.ext import commands

from database import (
    load_database,
    save_database,
    create_default_server_data
)


# =========================================================
# DATABASE HELPERS
# =========================================================

def ensure_server_data(data, guild_id):
    guild_id = str(guild_id)
    defaults = create_default_server_data()

    if guild_id not in data:
        data[guild_id] = defaults

    server_data = data[guild_id]

    # Migrate older database structures.
    if not isinstance(server_data.get("config"), dict):
        server_data["config"] = defaults["config"]

    if not isinstance(server_data.get("players"), dict):
        server_data["players"] = {}

    if not isinstance(server_data.get("transactions"), list):
        server_data["transactions"] = []

    # Ensure every configuration setting exists.
    for key, value in defaults["config"].items():
        server_data["config"].setdefault(key, value)

    return server_data


def get_config(guild_id):
    data = load_database()

    server_data = ensure_server_data(data, guild_id)

    save_database(data)

    return server_data["config"]


def update_config(guild_id, key, value):
    data = load_database()

    server_data = ensure_server_data(data, guild_id)

    server_data["config"][key] = value

    save_database(data)


# =========================================================
# SETTINGS EMBED
# =========================================================

def create_settings_embed(guild):
    config = get_config(guild.id)

    admin_role = (
        f"<@&{config['admin_role']}>"
        if config["admin_role"]
        else "Not configured"
    )

    log_channel = (
        f"<#{config['log_channel']}>"
        if config["log_channel"]
        else "Not configured"
    )

    embed = discord.Embed(
        title="Trade Horizon™ Configuration",
        description="Manage your server's economy settings.",
        color=discord.Color.from_rgb(144, 238, 144)
    )

    embed.add_field(
        name="Currency",
        value=f"{config['currency_emoji']} {config['currency_name']}",
        inline=True
    )

    embed.add_field(
        name="Starting Balance",
        value=f"{config['starting_balance']:,}",
        inline=True
    )

    embed.add_field(
        name="Admin Role",
        value=admin_role,
        inline=False
    )

    embed.add_field(
        name="Log Channel",
        value=log_channel,
        inline=False
    )

    embed.set_footer(
        text="Trade Horizon™ Economy System"
    )

    return embed


# =========================================================
# CURRENCY MODAL
# =========================================================

class CurrencyModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Set Currency")

        self.currency_name = discord.ui.TextInput(
            label="Currency Name",
            placeholder="Example: Coins",
            max_length=32
        )

        self.currency_emoji = discord.ui.TextInput(
            label="Currency Emoji",
            placeholder="Example: 🪙",
            max_length=16
        )

        self.add_item(self.currency_name)
        self.add_item(self.currency_emoji)

    async def on_submit(self, interaction: discord.Interaction):
        name = self.currency_name.value.strip()
        emoji = self.currency_emoji.value.strip()

        if not name or not emoji:
            await interaction.response.send_message(
                "❌ Currency name and emoji cannot be empty.",
                ephemeral=True
            )
            return

        update_config(
            interaction.guild_id,
            "currency_name",
            name
        )

        update_config(
            interaction.guild_id,
            "currency_emoji",
            emoji
        )

        await interaction.response.send_message(
            embed=create_settings_embed(interaction.guild),
            view=ConfigureView(),
            ephemeral=True
        )


# =========================================================
# STARTING BALANCE MODAL
# =========================================================

class StartingBalanceModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Set Starting Balance")

        self.balance = discord.ui.TextInput(
            label="Starting Balance",
            placeholder="Example: 100",
            max_length=15
        )

        self.add_item(self.balance)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.balance.value.strip())

            if amount < 0:
                raise ValueError

        except ValueError:
            await interaction.response.send_message(
                "❌ Enter a valid non-negative whole number.",
                ephemeral=True
            )
            return

        update_config(
            interaction.guild_id,
            "starting_balance",
            amount
        )

        await interaction.response.send_message(
            embed=create_settings_embed(interaction.guild),
            view=ConfigureView(),
            ephemeral=True
        )


# =========================================================
# ADMIN ROLE SELECTOR
# =========================================================

class AdminRoleSelect(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(
            placeholder="Select an admin role...",
            min_values=0,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        role = self.values[0] if self.values else None

        update_config(
            interaction.guild_id,
            "admin_role",
            role.id if role else None
        )

        await interaction.response.edit_message(
            content=None,
            embed=create_settings_embed(interaction.guild),
            view=ConfigureView()
        )


class AdminRoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

        self.add_item(AdminRoleSelect())


# =========================================================
# LOG CHANNEL SELECTOR
# =========================================================

class LogChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(
            placeholder="Select a log channel...",
            channel_types=[discord.ChannelType.text],
            min_values=0,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0] if self.values else None

        update_config(
            interaction.guild_id,
            "log_channel",
            channel.id if channel else None
        )

        await interaction.response.edit_message(
            content=None,
            embed=create_settings_embed(interaction.guild),
            view=ConfigureView()
        )


class LogChannelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

        self.add_item(LogChannelSelect())


# =========================================================
# RESET CONFIRMATION
# =========================================================

class ResetConfirmationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(
        label="Confirm",
        style=discord.ButtonStyle.danger
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        data = load_database()

        server_data = ensure_server_data(
            data,
            interaction.guild_id
        )

        defaults = create_default_server_data()

        # Reset configuration only.
        # Player balances and transaction history remain untouched.
        server_data["config"] = defaults["config"]

        save_database(data)

        await interaction.response.edit_message(
            content="✅ Configuration has been reset.",
            embed=None,
            view=None
        )

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.secondary
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.edit_message(
            content="Reset cancelled.",
            embed=None,
            view=None
        )


# =========================================================
# MAIN CONFIGURATION VIEW
# =========================================================

class ConfigureView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(
        label="Set Currency",
        emoji="🪙",
        style=discord.ButtonStyle.primary
    )
    async def set_currency(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_modal(CurrencyModal())

    @discord.ui.button(
        label="Set Starting Balance",
        emoji="💰",
        style=discord.ButtonStyle.primary
    )
    async def set_balance(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_modal(StartingBalanceModal())

    @discord.ui.button(
        label="Set Admin Role",
        emoji="🛡️",
        style=discord.ButtonStyle.primary
    )
    async def set_admin_role(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.edit_message(
            content="Select the administrator role:",
            embed=None,
            view=AdminRoleView()
        )

    @discord.ui.button(
        label="Set Log Channel",
        emoji="📋",
        style=discord.ButtonStyle.primary
    )
    async def set_log_channel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.edit_message(
            content="Select the transaction log channel:",
            embed=None,
            view=LogChannelView()
        )

    @discord.ui.button(
        label="Reset Configuration",
        emoji="♻️",
        style=discord.ButtonStyle.danger,
        row=2
    )
    async def reset_config(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.edit_message(
            content="⚠️ Are you sure you want to reset the configuration?",
            embed=None,
            view=ResetConfirmationView()
        )


# =========================================================
# /CONFIGURE COMMAND
# =========================================================

@app_commands.command(
    name="configure",
    description="Open the Trade Horizon™ configuration panel."
)
@app_commands.default_permissions(administrator=True)
async def configure_command(interaction: discord.Interaction):

    if interaction.guild is None:
        await interaction.response.send_message(
            "❌ This command can only be used inside a server.",
            ephemeral=True
        )
        return

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Only server administrators can configure Trade Horizon™.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        embed=create_settings_embed(interaction.guild),
        view=ConfigureView(),
        ephemeral=True
    )


# =========================================================
# SETUP
# =========================================================

def setup(bot: commands.Bot):
    bot.tree.add_command(configure_command)
