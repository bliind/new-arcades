import requests
import discord
import json
import re
from discord import app_commands
from discord.ext import commands
from urllib.parse import urlencode

headers = {
    'User-Agent': 'Arcades-Discord-Bot',
    'Accept': '*/*'
}

base_url = 'https://api.scryfall.com'

with open('manamojis.json') as s:
    global manamojis
    manamojis = json.load(s)

def make_embed(card, color='purple'):
    color = getattr(discord.Color, color)
    mana_cost = emojify_mana_cost(card['mana_cost'])
    embed = discord.Embed(
        title=f'{card["name"]} {mana_cost}',
        url=card['url'],
        color=color()
    )

    return embed

def emojify_mana_cost(mana_cost):
    mana_cost = mana_cost.lower()
    mana_cost = re.sub(r'\{(.?)\}', r'{mana\1}', mana_cost)
    mana_cost = mana_cost.format(**manamojis)

    return mana_cost

def call_api(endpoint, parameters=None):
    url = base_url + f'{endpoint}'
    if parameters:
        url += f'?{urlencode(parameters)}'
    resp = requests.get(url, headers=headers)
    return resp.json()

class Scryfall(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # add commands to the tree on load
    async def cog_load(self):
        # self.bot.command_list.append(self.reload_config)
        pass

    # remove commands from the tree on load
    async def cog_unload(self):
        # for server in self.bot.guilds:
            # self.bot.tree.remove_command('reload_config', guild=server)
        pass

    def make_card_object(self, data):
        card = {
            "name": data['name'],
            "mana_cost": data['mana_cost'],
            "type": data['type_line'],
            "text": data['oracle_text'],
            "url": data['scryfall_uri'],
            "images": data['image_uris'],
            "colors": data['colors'],
            "legalities": data['legalities'],
            "prices": data['prices'],
            "rulings_uri": data['rulings_uri'],
            "prints_search_uri": data['prints_search_uri'],
            "set_name": data['set_name']
        }

        try: card["flavor"] = data['flavor_text']
        except: pass
        try: card['power'] = data['power']
        except: pass
        try: card['toughness'] = data['toughness']
        except: pass
        try: card['loyalty'] = data['loyalty']
        except: pass

        return card

    async def find_card(self, query):
        data = call_api('/cards/search', {"q": query})

        if data['object'] == 'error':
            return data['details']

        # if more than 1, try fuzzy search.
        if data['total_cards'] > 1:
            data = call_api('/cards/named', {"fuzzy": query})
            if data['object'] == 'error':
                return data['details']
            return [self.make_card_object(data)]

        return [self.make_card_object(card) for card in data['data']]

    async def show_card(self, card, channel):
        embed = make_embed(card)

        embed.description = f'{card["type"]}\n'
        embed.description += emojify_mana_cost(card["text"]) + '\n'
        try: embed.description += f'_{card["flavor"]}_'
        except: pass
        try: embed.description += f'\n{card["power"]}/{card["toughness"]}'
        except: pass
        try: embed.description += f'\nLoyalty: {card["loyalty"]}'
        except: pass

        embed.set_thumbnail(url=card['images']['normal'])

        await channel.send(embed=embed)

    async def show_art_crop(self, card, channel):
        embed = make_embed(card)
        embed.set_image(url=card['images']['art_crop'])
        await channel.send(embed=embed)

    async def show_card_img(self, card, channel):
        embed = make_embed(card)
        embed.set_image(url=card['images']['large'])
        await channel.send(embed=embed)

    async def show_card_prices(self, card, channel):
        embed = make_embed(card)
        printings = call_api(card['prints_search_uri'].replace(base_url, ''))
        for printing in printings['data']:
            price_string = ''
            for unit, price in printing['prices'].items():
                if price:
                    if unit.startswith('usd'):
                        price_string += f'${price} • '
                    if unit.startswith('eur'):
                        price_string += f'€{price} • '
                    if unit == 'tix':
                        price_string += f'{price} TIX • '
            price_string = price_string[0:-3]
            embed.add_field(name=printing['set_name'], value=price_string)
        await channel.send(embed=embed)

    async def show_card_legalities(self, card, channel):
        embed = make_embed(card)
        for fmt, legality in card['legalities'].items():
            embed.add_field(name=fmt, value=legality)
        await channel.send(embed=embed)

    async def show_card_rulings(self, card, channel):
        embed = make_embed(card)
        rulings = call_api(card['rulings_uri'].replace(base_url, ''))
        embed.description = ''
        for ruling in rulings['data']:
            embed.description += f'**{ruling["published_at"]}**\n'
            embed.description += f'{ruling["comment"]}\n\n'
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        card_search = re.findall(r'\[\[(.+?)\]\]', message.content)
        for card_query in card_search:
            # check for flags
            art_crop = False
            card_img = False
            prices = False
            rulings = False
            legality = False
            if card_query.startswith('@'):
                art_crop = True
            if card_query.startswith('!'):
                card_img = True
            if card_query.startswith('$'):
                prices = True
            if card_query.startswith('?'):
                rulings = True
            if card_query.startswith('#'):
                legality = True

            if art_crop or card_img or prices or rulings or legality:
                card_query = card_query[1:]

            # if no flags, show regular cards
            cards = await self.find_card(card_query)

            if isinstance(cards, list):
                for card in cards:
                    if art_crop:
                        await self.show_art_crop(card, message.channel)
                    elif card_img:
                        await self.show_card_img(card, message.channel)
                    elif prices:
                        await self.show_card_prices(card, message.channel)
                    elif rulings:
                        await self.show_card_rulings(card, message.channel)
                    elif legality:
                        await self.show_card_legalities(card, message.channel)
                    else:
                        await self.show_card(card, message.channel)
            else:
                embed = discord.Embed(
                    color=discord.Color.red(),
                    title='Error',
                    description=cards
                )
                await message.channel.send(embed=embed)
