import os
import requests
import discord
import json
import re
import time
import asyncio
from discord import app_commands
from discord.ext import commands
from urllib.parse import urlencode

USER_AGENT = os.environ.get('MOXFIELD_UA')
headers = {
    'User-Agent': USER_AGENT,
    'Accept': '*'
}

base_url = 'https://api.moxfield.com/v2'

rate_limit = 1.5
last_api_call = 0

with open('manamojis.json') as s:
    global manamojis
    manamojis = json.load(s)

def emojify_mana_cost(mana_cost):
    callback = lambda g: f'{{mana{g.group(1).lower()}}}'
    mana_cost = re.sub(r'\{(.?\/?.?)\}', callback, mana_cost)
    mana_cost = mana_cost.replace('/', '').format(**manamojis)

    return mana_cost

async def get_deck_data(deck_id):
    global last_api_call
    current_time = time.time()
    time_since_last = current_time - last_api_call
    if time_since_last < rate_limit:
        await asyncio.sleep(rate_limit - time_since_last)

    url = f'{base_url}/decks/all/{deck_id}'
    resp = requests.get(url, headers=headers)
    return resp.json()

def get_types(cards, type):
    return list(filter(lambda x: type in x['card']['type_line'], cards))

def printable_card_list(cards, no_mana=True):
    output = ''
    for item in cards:
        card = item['card']
        if item['quantity'] > 1:
            output += f'{item["quantity"]}x '
        output += f'{card["name"]} '
        if 'mana_cost' in card:
            if not no_mana:
                output += emojify_mana_cost(card['mana_cost'])
        output += '\n'
    return output

def common_embed(data):
    deck_name = data['name']
    deck_format = data['format'].title()
    deck_link = data['publicUrl']

    embed = discord.Embed(
        color=discord.Color.purple(),
        title=f'{deck_name} ({deck_format})',
        url=deck_link
    )
    if 'main' in data:
        card_image_url = f'https://assets.moxfield.net/cards/card-{data["main"]["id"]}-art_crop.jpg'
        embed.set_thumbnail(url=card_image_url)
    else:
        embed.set_thumbnail(url='https://i.imgur.com/HKKheS6.png')
    embed.set_footer(icon_url='https://i.imgur.com/HKKheS6.png', text='Moxfield')

    return embed

def sort_by_usd(cards):
    def sort_callback(item):
        default_value = float('inf')
        key = 'usd_foil' if item['isFoil'] else 'usd'
        return float(item.get('card', {}).get('prices', {}).get(key, default_value))

    return sorted(cards, key=sort_callback, reverse=True)

def split_deck_into_types(deck):
    lands = get_types(deck, 'Land')
    creatures = get_types(deck, 'Creature')
    artifacts = get_types(deck, 'Artifact')
    instants = get_types(deck, 'Instant')
    sorceries = get_types(deck, 'Sorcery')
    enchantments = get_types(deck, 'Enchantment')
    planeswalkers = get_types(deck, 'Planeswalker')

    cards = {
        'Planeswalkers': sort_by_usd(planeswalkers),
        'Creatures': sort_by_usd(creatures),
        'Artifacts': sort_by_usd(artifacts),
        'Instants': sort_by_usd(instants),
        'Sorceries': sort_by_usd(sorceries),
        'Artifacts': sort_by_usd(artifacts),
        'Enchantments': sort_by_usd(enchantments),
        'Lands': sort_by_usd(lands),
    }

    return dict(sorted(cards.items(), key=lambda item: len(item[1]), reverse=True))

def cut_in_two(cardlist, total_chars):
    total_chars = sum(len(s) for s in cardlist)
    target_char_count = total_chars / 2

    current_char_count = 0
    split_index = 0

    for i, s in enumerate(cardlist):
        if current_char_count + len(s) >= target_char_count:
            split_index = i + 1
            break
        current_char_count += len(s)
        split_index = i + 1

    return (cardlist[0:split_index], cardlist[split_index:])

def cut_in_three(cardlist, total_chars):
    total_chars = sum(len(s) for s in cardlist)
    target_one_third = total_chars / 3
    target_two_thirds = 2 * total_chars / 3

    current_char_count = 0
    split_index_1 = 0
    split_index_2 = 0

    found_split_1 = False

    for i, s in enumerate(cardlist):
        current_char_count += len(s)
        if not found_split_1 and current_char_count >= target_one_third:
            split_index_1 = i + 1
            found_split_1 = True
        if found_split_1 and current_char_count >= target_two_thirds:
            split_index_2 = i + 1
            break

    first_third = cardlist[0:split_index_1]
    second_third = cardlist[split_index_1:split_index_2]
    third_third = cardlist[split_index_2:]

    return (first_third, second_third, third_third)

def fit_cardlist_text_in_field(label, cardlist):
    fields = []
    header = f'{label}: {sum(i["quantity"] for i in cardlist)}\n'
    printable = printable_card_list(cardlist)
    total_chars = len(printable)
    if total_chars > 1024:
        cards_as_list = printable.split('\n')
        first_half, second_half = cut_in_two(cards_as_list, total_chars)
        first_half = '\n'.join(first_half)
        second_half = '\n'.join(second_half)
        if len(first_half) > 1024 or len(second_half) > 1024:
            first_third, second_third, third_third = cut_in_three(cards_as_list, total_chars)
            first_third = '\n'.join(first_third)
            second_third = '\n'.join(second_third)
            third_third = '\n'.join(third_third)
            fields.append((header, first_third))
            fields.append(('', second_third))
            fields.append(('', third_third))
        else:
            fields.append((header, first_half))
            fields.append(('', second_half))
    else:
        fields.append((header, printable))

    return fields

def make_deck_embed(data):
    embed = common_embed(data)
    cards = split_deck_into_types(data['mainboard'].values())

    if 'commanders' in data:
        embed.description = '### Commanders:\n'
        for commander in data['commanders'].values():
            card_name = commander['card']['name']
            # if 'mana_cost' in commander['card']:
            #     card_name += f' {emojify_mana_cost(commander["card"]["mana_cost"])}'
            embed.description += f'{card_name}\n'

    field_count = 1
    for label, cardlist in cards.items():
        if len(cardlist) == 0: continue
        fields = fit_cardlist_text_in_field(label, cardlist)
        for field in fields:
            embed.add_field(name=field[0], value=field[1])
            if field_count == 2:
                embed.add_field(name='\u200b', value='\u200b')
                field_count = 0
            field_count += 1

    return embed

def make_collapsed_deck_embed(data):
    embed = common_embed(data)
    cards = split_deck_into_types(data['mainboard'].values())
    embed.description = ''

    if 'commanders' in data:
        embed.description += '### Commanders:\n'
        for commander in data['commanders'].values():
            card_name = commander['card']['name']
            # if 'mana_cost' in commander['card']:
            #     card_name += f' {emojify_mana_cost(commander["card"]["mana_cost"])}'
            embed.description += f'{card_name}\n'

    field_count = 1
    for label, cardlist in cards.items():
        if len(cardlist) == 0: continue
        header = f'{label}: {sum(i["quantity"] for i in cardlist)}'
        text = printable_card_list(cardlist[0:5])
        if len(cardlist) > 5:
            text += '...'
        embed.add_field(name=header, value=text)
        if field_count == 2:
            embed.add_field(name='\u200b', value='\u200b')
            field_count = 0
        field_count += 1

    return embed

class ExpandDeckView(discord.ui.View):
    def __init__(self, deckdata, timeout=None):
        super().__init__(timeout=timeout)
        self.deckdata = deckdata

    @discord.ui.button(label='View Full Deck', style=discord.ButtonStyle.primary)
    async def view_full_deck(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = make_deck_embed(self.deckdata)
        await interaction.response.send_message(embed=embed, ephemeral=True)

class Moxfield(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        deck_ids = re.findall(r'https://moxfield.com/decks/([^/>\s]*)', message.content)
        view = None
        embed = None
        if deck_ids:
            for deck_id in deck_ids:
                data = await get_deck_data(deck_id)
                if data['mainboardCount'] > 60:
                    view = ExpandDeckView(data)
                    embed = make_collapsed_deck_embed(data)
                else:
                    embed = make_deck_embed(data)
                await message.reply(embed=embed, view=view, mention_author=False)
