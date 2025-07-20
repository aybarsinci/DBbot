import os
from dotenv import load_dotenv
from discord import Object

load_dotenv()

TOKEN     = os.getenv("DISCORD_TOKEN")
GUILD_ID  = int(os.getenv("GUILD_ID"))
GUILD     = Object(id=GUILD_ID)
VALID_RANKS = ['Bronze', 'Silver', 'Gold', 'Platinum', 'Diamond', 'Ruby']
