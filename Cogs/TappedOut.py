import requests
import discord
import re
import io
import csv
from discord import app_commands
from discord.ext import commands
from urllib.parse import urlencode
from bs4 import BeautifulSoup

headers = {
    'User-Agent': 'Arcades-Discord-Bot',
    'Accept': '*/*'
}

def get_deck_cards(deck_url):
    parsed = []
    csv_resp = requests.get(f'{deck_url}?fmt=csv', headers=headers)
    csv_file = io.StringIO(csv_resp.text)
    dict_reader = csv.DictReader(csv_file)

    for row in dict_reader:
        parsed.append(row)

    return parsed

def get_deck_title(deck_url):
    resp = requests.get(deck_url)
    soup = BeautifulSoup(resp.text, 'html.parser')
    if soup.title:
        return soup.title.string
    return 'MTG Deck'

def get_deck_data(deck_url):
    cards = get_deck_cards(deck_url)
    title = get_deck_title(deck_url)

    return {"cards": cards, "title": title}

def split_into_three(input):
    n = len(input)
    if n == 0:
        return [], [], []
    base_length = n / 3
    remainder = n % 3

    length1 = int(base_length + (1 if remainder > 0 else 0))
    length2 = int(base_length + (1 if remainder > 1 else 0))

    o1 = input[0:length1]
    o2 = input[length1:length1 + length2]
    o3 = input[length1 + length2:]

    return o1, o2, o3

def get_name_and_qty(card):
    string = '- '
    string += f'{card["Qty"]}x ' if int(card['Qty']) > 1 else ''
    string += card['Name']
    return string

def make_embed(cards, deck_url, deck_name = ''):
    embed = discord.Embed(
        color=discord.Color.blue(),
        description='',
        title=deck_name,
        url=deck_url
    )
    try: cmdr = [c for c in cards if c['Commander']][0]
    except: cmdr = {"Name": ""}

    if cmdr['Name']:
        embed.description = f'## Commander: {cmdr["Name"]}\n\n'

    mainboard = list(filter(lambda x: x['Board'] == 'main' and x['Name'] != cmdr['Name'], cards))
    p1, p2, p3 = split_into_three(mainboard)

    embed.add_field(name='', value='\n'.join(list(map(get_name_and_qty, p1))))
    embed.add_field(name='', value='\n'.join(list(map(get_name_and_qty, p2))))
    embed.add_field(name='', value='\n'.join(list(map(get_name_and_qty, p3))))

    return embed

class TappedOut(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        deck_links = re.findall(r'(https://tappedout.net/mtg-decks/[^>]*)', message.content)
        if deck_links:
            for deck_link in deck_links:
                data = get_deck_data(deck_link)
                embed = make_embed(data['cards'], deck_link, data['title'])
                await message.reply(embed=embed, mention_author=False)
