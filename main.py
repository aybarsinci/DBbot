import asyncio
import discord
from discord.ext import commands

from config import TOKEN, GUILD
import database

async def main():
    # Initialize the SQLite database
    database.init_db()

    # Create the bot with member intent
    intents = discord.Intents.default()
    intents.members = True
    bot = commands.Bot(command_prefix='!', intents=intents)

    # Load our cogs (commands & background tasks)
    await bot.load_extension('cogs.commands')
    await bot.load_extension('cogs.tasks')

    # Sync slash‑commands once ready
    @bot.event
    async def on_ready():
        print(f'✅ Bot logged in as {bot.user}')
        synced = await bot.tree.sync(guild=GUILD)
        print(f'🔄 Synced {len(synced)} commands')

    # Run the bot
    await bot.start(TOKEN)

if __name__ == '__main__':
    asyncio.run(main())
