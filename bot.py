import os
import sqlite3
import requests
import discord
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv

# ─── Load config ────────────────────────────────────────────────────────────────
load_dotenv()
TOKEN    = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID'))
GUILD    = discord.Object(id=GUILD_ID)

# ─── Database setup ─────────────────────────────────────────────────────────────
conn = sqlite3.connect('links.db')
c = conn.cursor()
c.execute('''
  CREATE TABLE IF NOT EXISTS links (
    discord_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL
  )
''')
conn.commit()

# ─── Helper: fetch Season 7 entry ───────────────────────────────────────────────
def fetch_season7_entry(name: str, platform: str = "crossplay"):
    url = f"https://api.the-finals-leaderboard.com/v1/leaderboard/s7/{platform}"
    resp = requests.get(url, params={"name": name})
    resp.raise_for_status()
    entries = resp.json().get("data", [])
    return entries[0] if entries else None

VALID_RANKS = ['Bronze', 'Silver', 'Gold', 'Platinum', 'Diamond', 'Ruby']

# ─── Bot setup ─────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'✅ Bot logged in as {bot.user}')
    try:
        synced = await bot.tree.sync(guild=GUILD)
        print(f'🔄 Synced {len(synced)} slash‑commands to guild {GUILD_ID}')
    except Exception as e:
        print('❌ Slash‑command sync failed:', e)
    if not refresh_all_ranks.is_running():
        refresh_all_ranks.start()

# ─── Background task: refresh everyone’s roles every 15 minutes ──────────────
@tasks.loop(minutes=15)
async def refresh_all_ranks():
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return

    c.execute('SELECT discord_id, account_id FROM links')
    for discord_id, account_id in c.fetchall():
        member = guild.get_member(int(discord_id))
        if not member:
            continue

        try:
            entry = fetch_season7_entry(account_id)
        except requests.HTTPError:
            continue
        if not entry:
            continue

        league = entry.get("league", "")
        broad = league.split()[0] if league else "Unranked"
        if broad not in VALID_RANKS:
            broad = "Unranked"

        current = {r.name for r in member.roles}
        if broad in current:
            continue

        # remove old tier roles
        to_remove = [r for r in member.roles if r.name in VALID_RANKS]
        if to_remove:
            await member.remove_roles(*to_remove, reason="Auto rank refresh")

        # get or create new role
        role = discord.utils.get(guild.roles, name=broad)
        if role is None:
            try:
                role = await guild.create_role(name=broad, reason="Auto‑creating rank role")
            except discord.Forbidden:
                continue

        await member.add_roles(role, reason="Auto rank refresh")

# ─── /link command ──────────────────────────────────────────────────────────────
@bot.tree.command(
    guild=GUILD,
    name='link',
    description='🔗 Link your Finals (Embark) name and assign your Season 7 role'
)
@app_commands.describe(account='Your Embark display name (e.g. Player#1234)')
async def link(interaction: discord.Interaction, account: str):
    c.execute(
        'REPLACE INTO links(discord_id,account_id) VALUES(?,?)',
        (str(interaction.user.id), account)
    )
    conn.commit()

    try:
        entry = fetch_season7_entry(account)
    except requests.HTTPError:
        return await interaction.response.send_message(
            '⚠️ Error fetching leaderboard. Try again later.', ephemeral=True
        )

    if not entry:
        return await interaction.response.send_message(
            f'🔗 Linked `{account}`, but no Season 7 entry found.', ephemeral=True
        )

    league = entry.get("league", "")
    broad = league.split()[0] if league else "Unranked"
    if broad not in VALID_RANKS:
        broad = "Unranked"

    member = interaction.user
    to_remove = [r for r in member.roles if r.name in VALID_RANKS]
    if to_remove:
        await member.remove_roles(*to_remove, reason='Updating Season 7 rank')

    role = discord.utils.get(interaction.guild.roles, name=broad)
    if role is None:
        try:
            role = await interaction.guild.create_role(name=broad, reason="Auto‑creating rank role")
        except discord.Forbidden:
            return await interaction.response.send_message(
                f'✅ Linked `{account}`, but cannot create `{broad}` role. '
                'Please create it manually.', ephemeral=True
            )

    await member.add_roles(role, reason='Assigned by rank‑bot')
    await interaction.response.send_message(
        f'✅ Linked `{account}` and assigned **{broad}** role.', ephemeral=True
    )

# ─── /rank command ──────────────────────────────────────────────────────────────
@bot.tree.command(
    guild=GUILD,
    name='rank',
    description='🎖️ Show a player’s Season 7 stats'
)
@app_commands.describe(
    member='Discord member to lookup',
    embark='Or specify an Embark ID (e.g. Player#1234)'
)
async def rank(
    interaction: discord.Interaction,
    member: discord.Member = None,
    embark: str = None
):
    # Ensure only one of member or embark is provided
    if member and embark:
        return await interaction.response.send_message(
            '❌ Please specify **either** a Discord member **or** an Embark ID, not both.'
        )

    # Determine the account ID to lookup
    if embark:
        account = embark
        display_name = embark
    else:
        target = member or interaction.user
        display_name = target.display_name
        c.execute(
            'SELECT account_id FROM links WHERE discord_id = ?',
            (str(target.id),)
        )
        row = c.fetchone()
        if not row:
            return await interaction.response.send_message(
                f'❌ {display_name} has not linked an account. '
                'Use `/link YourName#1234` first.'
            )
        account = row[0]

    # Fetch leaderboard entry
    try:
        entry = fetch_season7_entry(account)
    except requests.HTTPError:
        return await interaction.response.send_message(
            '⚠️ Error fetching leaderboard. Try again later.'
        )
    if not entry:
        return await interaction.response.send_message(
            f'⚠️ No Season 7 entry found for `{account}`.'
        )

    # Extract stats
    league       = entry.get("league", "Unranked")
    numeric_rank = entry.get("rank", "N/A")
    points       = entry.get("rankScore", "N/A")

    # Public reply
    msg = (
        f'**{display_name}**ʼs Season 7 Stats:\n'
        f'• 👤 Embark ID: `{account}`\n'
        f'• 🏆 League: **{league}**\n'
        f'• 🔢 Rank: **{numeric_rank}**\n'
        f'• 💎 Points: **{points}**'
    )
    await interaction.response.send_message(msg)

# ─── Run the bot ────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    bot.run(TOKEN)
