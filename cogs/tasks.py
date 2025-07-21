import discord
import requests
from discord.ext import commands, tasks
from datetime import datetime

from config import GUILD_ID, VALID_RANKS
from database import c
from api import fetch_season7_entry

class RankManagerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.refresh_all_ranks.is_running():
            self.refresh_all_ranks.start()

    @tasks.loop(minutes=3)
    async def refresh_all_ranks(self):
        start_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{start_ts}] 🔄 Refreshing all linked users' ranks…")

        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            print(f"[{start_ts}] ❌ Guild not found, skipping refresh.")
            return

        c.execute('SELECT discord_id, account_id FROM links')
        for discord_id, account_id in c.fetchall():
            member = guild.get_member(int(discord_id))
            if not member:
                continue

            # 1) Fetch with timeout and robust error handling
            try:
                entry = fetch_season7_entry(account_id, timeout=5.0)
            except (requests.HTTPError, requests.RequestException) as e:
                print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] ⚠️ Skipping {account_id}: {e}")
                continue
            if not entry:
                continue

            # 2) Compute the broad tier
            league = entry.get("league", "")
            broad  = league.split()[0] if league else "Unranked"
            if broad not in VALID_RANKS:
                broad = "Unranked"

            # 3) Only proceed if they actually need a new tier
            current = {r.name for r in member.roles}
            if broad in current:
                continue

            # 4) Remove any old tier roles, catching permission errors
            old_roles = [r for r in member.roles if r.name in VALID_RANKS]
            if old_roles:
                try:
                    await member.remove_roles(*old_roles, reason="Auto rank refresh")
                except discord.Forbidden:
                    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] ⚠️ Cannot remove roles from {member.display_name}, missing permissions.")
                    continue

            # 5) Get or create the new role, catching permission errors
            role = discord.utils.get(guild.roles, name=broad)
            if role is None:
                try:
                    role = await guild.create_role(name=broad, reason="Auto‑creating rank role")
                except discord.Forbidden:
                    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] ⚠️ Cannot create role {broad}, missing permissions.")
                    continue

            # 6) Assign the new role, catching permission errors
            try:
                await member.add_roles(role, reason="Auto rank refresh")
            except discord.Forbidden:
                print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] ⚠️ Cannot add role {broad} to {member.display_name}, missing permissions.")
                continue

        end_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{end_ts}] ✅ Finished refreshing ranks")

async def setup(bot: commands.Bot):
    await bot.add_cog(RankManagerCog(bot))
