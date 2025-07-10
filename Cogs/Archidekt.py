import requests
import discord
import re
import io
import csv
from discord import app_commands
from discord.ext import commands
from urllib.parse import urlencode
headers = {
    'User-Agent': 'Arcades-Discord-Bot',
    'Accept': '*/*'
}

BASE_URL = 'https://archidekt.com/api'
LINK_BASE_URL = 'https://archidekt.com'
FORMATS = {
    1: "Standard",
    2: "Modern",
    3: "Commander",
    4: "Legacy",
    5: "Vintage",
    6: "Pauper",
    7: "Custom",
    8: "Frontier",
    9: "Future Standard",
    10: "Penny Dreadful",
    11: "1v1 Commander",
    12: "Duel Commander",
    13: "Standard Brawl",
    14: "Oathbreaker",
    15: "Pioneer",
    16: "Historic",
    17: "Pauper EDH",
    18: "Alchemy",
    20: "Brawl",
    21: "Gladiator",
    22: "Premodern",
    23: "PreDH",
    24: "Timeless",
    25: "Canadian Highlander"
}

def get_deck_data(deckID):
    resp = requests.get(f'{BASE_URL}/decks/{deckID}/')
    data = resp.json()

    output = {
        "id": deckID,
        "name": data['name'],
        "thumbnail": data['featured'],
        "cards": {
            "Planeswalker": [],
            "Creature": [],
            "Artifact": [],
            "Instant": [],
            "Sorcery": [],
            "Artifact": [],
            "Enchantment": [],
            "Land": [],
        }
    }

    try: output['format'] = FORMATS[data['deckFormat']]
    except: output['format'] = ''

    for card in data['cards']:
        card_name = ''
        quantity = card['quantity']
        if quantity > 1:
            card_name = f'{quantity}x '
        card_name += card['card']['oracleCard']['name']

        for card_type in output['cards'].keys():
            if card_type in card['card']['oracleCard']['types']:
                output['cards'][card_type].append((quantity, card_name))

    return output

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

def make_deck_embed(deck_data, full_view=False):
    title = deck_data['name']
    if deck_data['format']:
        title += f' ({deck_data["format"]})'
    embed = discord.Embed(
        color=discord.Color.blue(),
        title=title,
        url=f'{LINK_BASE_URL}/{deck_data["id"]}',
        description=''
    )
    embed.set_thumbnail(url=deck_data['thumbnail'])
    embed.set_footer(text='Archidekt.com')

    types = dict(sorted(deck_data['cards'].items(), key=lambda item: len(item[1]), reverse=True))

    compact = sum(len(f) for f in deck_data['cards'].values()) > 50

    fields = []
    for type, cards in types.items():
        if len(cards) == 0: continue
        header = f'{type} ({sum(c[0] for c in cards)})'
        rest = ''

        if compact and not full_view:
            for quantity, card_name in cards[0:5]:
                rest += f'{card_name}\n'
            if len(cards) > 5:
                rest += '...'
        else:
            for quantity, card_name in cards:
                rest += f'{card_name}\n'

        total_chars = len(rest)
        if total_chars > 1024:
            first_half, second_half = cut_in_two(rest.split('\n'), total_chars)
            fields.append((header, '\n'.join(first_half)))
            fields.append(('', '\n'.join(second_half)))
        else:
            fields.append((header, rest))

    field_count = 1
    for field in fields:
        embed.add_field(name=field[0], value=field[1])
        if field_count == 2:
            embed.add_field(name='\u200b', value='\u200b')
            field_count = 0
        field_count += 1

    return embed, compact

class ExpandDeckView(discord.ui.View):
    def __init__(self, deck_data, timeout=None):
        super().__init__(timeout=timeout)
        self.deck_data = deck_data

    @discord.ui.button(label='View Full Deck', style=discord.ButtonStyle.primary)
    async def view_full_deck(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed, compact = make_deck_embed(self.deck_data, full_view=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

class Archidekt(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        deck_ids = re.findall(r'https://archidekt.com/decks/([^/>]*)', message.content)
        if deck_ids:
            for deck_id in deck_ids:
                deck_data = get_deck_data(deck_id)
                embed, compact = make_deck_embed(deck_data)
                if compact:
                    view = ExpandDeckView(deck_data)
                else:
                    view = None

                await message.reply(embed=embed, view=view, mention_author=False)
