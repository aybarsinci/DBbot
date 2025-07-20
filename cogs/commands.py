import discord
import requests
from discord.ext import commands
from discord import app_commands

from config import GUILD, VALID_RANKS
from database import c, conn
from api import fetch_season7_entry

class CommandCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name='link',
        description='🔗 Link your Embark name and assign your Season 7 role'
    )
    @app_commands.guilds(GUILD)
    @app_commands.describe(account='Your Embark name, e.g. Player#1234')
    async def link(self, interaction: discord.Interaction, account: str):
        # Store the mapping
        c.execute(
            'REPLACE INTO links(discord_id, account_id) VALUES (?, ?)',
            (str(interaction.user.id), account)
        )
        conn.commit()

        # Fetch the leaderboard entry
        try:
            entry = fetch_season7_entry(account)
        except requests.HTTPError:
            await interaction.response.send_message(
                '⚠️ Could not fetch leaderboard. Try again later.',
                ephemeral=True
            )
            return

        if not entry:
            await interaction.response.send_message(
                f'🔗 Linked `{account}`, but no Season 7 entry found.',
                ephemeral=True
            )
            return

        # Determine broad rank
        league = entry.get("league", "")
        broad  = league.split()[0] if league else "Unranked"
        if broad not in VALID_RANKS:
            broad = "Unranked"

        # Remove old roles & assign new
        member    = interaction.user
        to_remove = [r for r in member.roles if r.name in VALID_RANKS]
        if to_remove:
            await member.remove_roles(*to_remove, reason='Updating Season 7 rank')

        role = discord.utils.get(interaction.guild.roles, name=broad)
        if role is None:
            try:
                role = await interaction.guild.create_role(
                    name=broad,
                    reason="Auto‑creating rank role"
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    f'✅ Linked `{account}`, but cannot create role `{broad}`. '
                    'Please create it manually.',
                    ephemeral=True
                )
                return

        await member.add_roles(role, reason='Assigned by rank‑bot')
        await interaction.response.send_message(
            f'✅ Linked `{account}` and assigned **{broad}** role.',
            ephemeral=True
        )

    @app_commands.command(
        name='rank',
        description='🎖️ Show a player’s Season 7 stats'
    )
    @app_commands.guilds(GUILD)
    @app_commands.describe(
        member='Discord member to lookup',
        embark='Or specify an Embark ID directly (e.g. Player#1234)'
    )
    async def rank(
        self,
        interaction: discord.Interaction,
        member: discord.Member = None,
        embark: str = None
    ):
        # Only one of member or embark may be provided
        if member and embark:
            await interaction.response.send_message(
                '❌ Please specify either a Discord member or an Embark ID, not both.'
            )
            return

        # Determine which account to lookup
        if embark:
            account      = embark
            display_name = embark
        else:
            target       = member or interaction.user
            display_name = target.display_name
            c.execute(
                'SELECT account_id FROM links WHERE discord_id = ?',
                (str(target.id),)
            )
            row = c.fetchone()
            if not row:
                await interaction.response.send_message(
                    f'❌ {display_name} has not linked an account. '
                    'Use `/link YourName#1234` first.'
                )
                return
            account = row[0]

        # Fetch the entry
        try:
            entry = fetch_season7_entry(account)
        except requests.HTTPError:
            await interaction.response.send_message(
                '⚠️ Could not fetch leaderboard. Try again later.'
            )
            return
        if not entry:
            await interaction.response.send_message(
                f'⚠️ No Season 7 entry found for `{account}`.'
            )
            return

        # Extract stats
        league       = entry.get("league",   "Unranked")
        numeric_rank = entry.get("rank",     "N/A")
        points       = entry.get("rankScore","N/A")

        # Public reply
        msg = (
            f'**{display_name}**’s Season 7 Stats:\n'
            f'• 👤 Embark ID: `{account}`\n'
            f'• 🏆 League: **{league}**\n'
            f'• 🔢 Rank: **{numeric_rank}**\n'
            f'• 💎 Points: **{points}**'
        )
        await interaction.response.send_message(msg)

async def setup(bot: commands.Bot):
    await bot.add_cog(CommandCog(bot))
