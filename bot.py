import discord
from discord import app_commands
from discord.ext import commands
import importlib
import os
import sys
import asyncio

# extend bot class
class MyBot(commands.Bot):
    def __init__(self, use_cogs):
        intents = discord.Intents.default()
        intents.message_content = True
        self.use_cogs = use_cogs
        super().__init__(command_prefix='¤', intents=intents)
        self.synced = False

    async def setup_hook(self):
        for cog in self.use_cogs:
            module = getattr(importlib.import_module(f'Cogs.{cog}'), cog)
            await self.add_cog(module(self))

    async def on_ready(self):
        if self.synced:
            return

        # sleep then sync
        await asyncio.sleep(1)
        await self.tree.sync()
        self.synced = True

        print('Bot ready to go!')

    @app_commands.command(name='cog_reload', description='Reload a Cog on the bot')
    async def cog_reload(self, interaction: discord.Interaction, cog: str):
        await interaction.response.defer(ephemeral=True)

        if cog in self.use_cogs:
            # remove the Cog from the bot
            removed = await self.remove_cog(cog)
            if not removed:
                await interaction.followup.send(f'Error unloading Cog `{cog}`')
                return

            # re-import the Cog module
            module = sys.modules[f'Cogs.{cog}']
            importlib.reload(module)
            # re-add the Cog class
            myclass = getattr(sys.modules[f'Cogs.{cog}'], cog)
            await self.add_cog(myclass(self))

            # sleep then sync
            await asyncio.sleep(1)
            for server in self.bot.guilds:
                await self.tree.sync(guild=server)

            await interaction.followup.send(f'Reloaded `{cog}`')
        else:
            await interaction.followup.send(f'Unknown Cog: {cog}')

bot = MyBot(['Scryfall', 'TappedOut', 'Moxfield', 'Archidekt', 'Utility'])
bot.run(os.getenv('BOT_TOKEN'))
