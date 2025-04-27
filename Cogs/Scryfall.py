import requests
import discord
import json
import re
from thefuzz import fuzz
from discord import app_commands
from discord.ext import commands
from urllib.parse import urlencode

tree = None

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
    # mana_cost = emojify_mana_cost(card['mana_cost'])
    # title=f'{card["name"]} {mana_cost}'
    embed = discord.Embed(
        description='',
        url=card['scryfall_uri'],
        color=color()
    )
    embed.title = card['name']
    if 'mana_cost' in card:
        embed.title += f' {emojify_mana_cost(card["mana_cost"])}'

    return embed

def emojify_mana_cost(mana_cost):
    callback = lambda g: f'{{mana{g.group(1).lower()}}}'
    mana_cost = re.sub(r'\{(.?)\}', callback, mana_cost)
    mana_cost = mana_cost.format(**manamojis)

    return mana_cost

def call_api(endpoint, parameters=None):
    url = base_url + f'{endpoint}'
    if parameters:
        url += f'?{urlencode(parameters)}'
    resp = requests.get(url, headers=headers)
    return resp.json()

def card_obj(data):
    card = {}
    fields = [
        'name',
        'mana_cost',
        'type_line',
        'oracle_text',
        'scryfall_uri',
        'image_uris',
        'colors',
        'legalities',
        'prices',
        'rulings_uri',
        'prints_search_uri',
        'set_name',
        'flavor_text',
        'power',
        'toughness',
        'loyalty',
        'card_faces',
        'layout'
    ]

    for field in fields:
        try: card[field] = data[field]
        except: pass

    return card


class Scryfall(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def make_card_object(self, data):
        cards = []

        card = card_obj(data)
        return [card]
        if 'card_faces' in data:
            for face in data['card_faces']:
                face_card = dict(card)
                face_card.update(card_obj(face))
                cards.append(face_card)
        else:
            cards.append(card)

        return cards

    async def find_card(self, query):
        search = call_api('/cards/search', {"q": query})
        fuzzy = call_api('/cards/named', {"fuzzy": query})

        # try to return fuzzy first
        if fuzzy['object'] == 'error':
            if search['object'] == 'error':
                return search['details']

            if search['total_cards'] > 1:
                if search['total_cards'] > 8:
                    return f'Too many cards match "{query}", please narrow your query.'
                # if a few objects, list the options
                output = {"cards": []}
                for card in search['data']:
                    label = f'{card["name"]}'
                    if 'mana_cost' in card:
                        label += f' {card["mana_cost"]}'
                    if 'card_faces' in card and 'mana_cost' in card['card_faces'][0]:
                        label +=f' {card["card_faces"][0]["mana_cost"]}'
                    card_string = f'- [{label}]({card["scryfall_uri"]})'
                    output['cards'].append(f'{emojify_mana_cost(card_string)}')
                return output

            return self.make_card_object(search['data'][0])
        return self.make_card_object(fuzzy)

    async def show_card(self, card):
        embed = make_embed(card)
        if 'card_faces' in card:
            for index, face in enumerate(card['card_faces']):
                if index == 0:
                    embed.title = face['name']
                    if 'mana_cost' in face:
                        embed.title += f' {emojify_mana_cost(face["mana_cost"])}'
                    try:
                        embed.set_thumbnail(url=face['image_uris']['normal'])
                    except:
                        embed.set_thumbnail(url=card['image_uris']['normal'])
                else:
                    embed.description += f'**{face["name"]}**'
                    if 'mana_cost' in face:
                        embed.description += f' {emojify_mana_cost(face["mana_cost"])}'
                    embed.description += '\n'
                embed.description += f'{face["type_line"]}\n'
                embed.description += emojify_mana_cost(face['oracle_text'])
                try: embed.description += f'\n_{face["flavor_text"]}_'
                except: pass
                try: embed.description += f'\n{face["power"]}/{face["toughness"]}'
                except: pass
                try: embed.description += f'\nLoyalty: {face["loyalty"]}'
                except: pass

                if index == 0:
                    embed.description += '\n---------\n'
        else:
            embed.title = card['name']
            if 'mana_cost' in card:
                embed.title += f' {emojify_mana_cost(card["mana_cost"])}'
            embed.description = f'{card["type_line"]}\n'
            embed.description += emojify_mana_cost(card["oracle_text"]) + '\n'
            try: embed.description += f'_{card["flavor_text"]}_'
            except: pass
            try: embed.description += f'\n{card["power"]}/{card["toughness"]}'
            except: pass
            try: embed.description += f'\nLoyalty: {card["loyalty"]}'
            except: pass
            embed.set_thumbnail(url=card['image_uris']['normal'])

        return embed

    async def show_art_crop(self, card, query):
        embed = make_embed(card)
        if 'card_faces' in card and card['layout'] != 'adventure':
            for face in card['card_faces']:
                if fuzz.ratio(query.lower(), face['name'].lower()) > 40:
                    embed.set_image(url=face['image_uris']['art_crop'])
        else:
            embed.set_image(url=card['image_uris']['art_crop'])
        return embed

    async def show_card_img(self, card, query):
        embed = make_embed(card)
        if 'card_faces' in card and card['layout'] != 'adventure':
            for face in card['card_faces']:
                if fuzz.ratio(query.lower(), face['name'].lower()) > 40:
                    embed.set_image(url=face['image_uris']['large'])
        else:
            embed.set_image(url=card['image_uris']['large'])
        return embed

    async def show_card_prices(self, card):
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
        return embed

    async def show_card_legalities(self, card):
        embed = make_embed(card)
        for fmt, legality in card['legalities'].items():
            embed.add_field(name=fmt, value=legality)
        return embed

    async def show_card_rulings(self, card):
        embed = make_embed(card)
        rulings = call_api(card['rulings_uri'].replace(base_url, ''))
        embed.description = ''
        for ruling in rulings['data']:
            embed.description += f'**{ruling["published_at"]}**\n'
            embed.description += f'{ruling["comment"]}\n\n'
        return embed

    @commands.Cog.listener()
    async def on_message(self, message):
        card_search = re.findall(r'\[\[(.+?)\]\]', message.content)
        if card_search:
            embeds = await self.get_card(card_search)
            for embed in embeds:
                await message.channel.send(embed=embed)

    async def get_card(self, card_search):
        embeds = []
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
                        embeds.append(await self.show_art_crop(card, card_query))
                    elif card_img:
                        embeds.append(await self.show_card_img(card, card_query))
                    elif prices:
                        embeds.append(await self.show_card_prices(card))
                    elif rulings:
                        embeds.append(await self.show_card_rulings(card))
                    elif legality:
                        embeds.append(await self.show_card_legalities(card))
                    else:
                        embeds.append(await self.show_card(card))
            elif isinstance(cards, dict):
                description = '\n'.join(cards['cards'])
                embed = discord.Embed(
                    color=discord.Color.greyple(),
                    title='Multiple Cards Match',
                    description=description
                )
                embeds.append(embed)
            else:
                embed = discord.Embed(
                    color=discord.Color.red(),
                    title='Error',
                    description=cards
                )
                embeds.append(embed)

        return embeds

    @app_commands.command(name='scryfall', description='Get a Scryfall search going')
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def scryfall(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(ephemeral=False)
        embeds = await self.get_card([query])
        for embed in embeds:
            await interaction.followup.send(embed=embed, ephemeral=False)
