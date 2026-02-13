import random
import discord
from discord import app_commands
from discord.ext import commands

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='roll', description='Roll dice')
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def roll_command(self, interaction: discord.Interaction, dice: str):
        try:
            number, sides = dice.split('d')
        except ValueError:
            await interaction.response.send_message('Invalid dice format. Please use the format "XdY" where X is the number of dice and Y is the number of sides.', ephemeral=True)
            return

        results = []
        for _ in range(int(number)):
            results.append(random.randint(1, int(sides)))

        message = f'{sum(results)}'
        if int(number) > 1:
            message += f'\n-# {number} d{sides}s: ' + ', '.join(map(str, results))
        await interaction.response.send_message(message)
