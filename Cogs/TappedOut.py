import requests
import discord
import re
import io
import csv
from discord import app_commands
from discord.ext import commands
from urllib.parse import urlencode
from bs4 import BeautifulSoup, NavigableString

headers = {
    'User-Agent': 'Arcades-Discord-Bot',
    'Accept': '*/*'
}

def get_deck_data(stub):
    url = f'https://tappedout.net/api/deck/widget/?deck={stub}&cols=10'
    resp = requests.get(url, headers=headers)
    data = resp.json()

    deck_title = data['title']
    deck_url = data['url']

    board_html = data['board']
    soup = BeautifulSoup(board_html, 'html.parser')

    columns = soup.find_all('div', class_='tappedout-board-col')
    fields = {}
    for column in columns:
        header = column.find('h3')
        if header == None: continue

        fields[header.text] = []

        list_items = column.find_all('li', class_='tappedout-member')
        for list_item in list_items:
            card_text = ''
            quantity = "".join([t for t in list_item.contents if type(t) == NavigableString]).strip()
            card_name = list_item.find('a', class_='card-link').text
            if quantity == '1x':
                card_text += f'{card_name}'
            else:
                card_text += f'{quantity} {card_name}'
            fields[header.text].append(card_text)

    return deck_title, deck_url, fields

def make_deck_embed(deck_title, deck_url, fields, full_view=False):
    embed = discord.Embed(
        color=discord.Color.blue(),
        title=deck_title,
        url=deck_url,
        description=''
    )
    embed.set_thumbnail(url='https://s.tappedout.net/s1/img/2017-4.85563b67c976.png')
    embed.set_footer(text='TappedOut.net')
    if 'Commander' in fields:
        embed.description = '### Commanders:\n'
        embed.description += '\n'.join(fields['Commander'])

    sorted_fields = dict(sorted(fields.items(), key=lambda item: len(item[1]), reverse=True))

    unique_cards = sum(len(c) for c in sorted_fields.values())
    compact = unique_cards > 50
    field_count = 1
    for label, cards in sorted_fields.items():
        if label == 'Commander': continue

        if compact and not full_view:
            smol = cards[0:5]
            if len(cards) > 5:
                smol.append('...')
            embed.add_field(name=label, value='\n'.join(smol))
        else:
            embed.add_field(name=label, value='\n'.join(cards))
        if field_count == 2:
            embed.add_field(name='\u200b', value='\u200b')
            field_count = 0
        field_count += 1

    return embed, compact

class ExpandDeckView(discord.ui.View):
    def __init__(self, deck_title, deck_url, fields, timeout=None):
        super().__init__(timeout=timeout)
        self.deck_title = deck_title
        self.deck_url = deck_url
        self.fields = fields

    @discord.ui.button(label='View Full Deck', style=discord.ButtonStyle.primary)
    async def view_full_deck(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed, compact = make_deck_embed(self.deck_title, self.deck_url, self.fields, full_view=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

class TappedOut(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        deck_stubs = re.findall(r'https://tappedout.net/mtg-decks/([^/>]*)', message.content)
        if deck_stubs:
            for deck_stub in deck_stubs:
                deck_title, deck_url, fields = get_deck_data(deck_stub)
                embed, compact = make_deck_embed(deck_title, deck_url, fields)
                if compact:
                    view = ExpandDeckView(deck_title, deck_url, fields)
                else:
                    view = None

                await message.reply(embed=embed, view=view, mention_author=False)
