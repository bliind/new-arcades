import os
import asyncio
import discord
from discord.ext import commands

from Cogs.Archidekt import Archidekt
from Cogs.Moxfield import Moxfield
from Cogs.TappedOut import TappedOut
from Cogs.Scryfall import Scryfall
from Cogs.Utility import Utility

class MyBot(commands.Bot):
    def __init__(self, use_cogs):
        intents = discord.Intents.default()
        intents.message_content = True
        self.use_cogs = use_cogs
        super().__init__(command_prefix='¤', intents=intents)
        self.synced = False

    async def setup_hook(self):
        for use_cog in self.use_cogs:
            await self.add_cog(use_cog(self))

    async def on_ready(self):
        if self.synced:
            return

        await asyncio.sleep(1)
        await self.tree.sync()
        self.synced = True

        print('Bot ready to go!')

bot = MyBot([
    Scryfall,
    TappedOut,
    Moxfield,
    Archidekt,
    Utility
])

bot.run(os.getenv('BOT_TOKEN', ''))
