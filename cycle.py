import asyncio
import discord,secrets, utility, random, datetime, os, urllib.request, difflib
from discord.ext import commands
from discord import Webhook, app_commands
from bs4 import BeautifulSoup

BASE_URL = 'https://tcf-info.com/'

class Cycle(commands.Cog):
    def __init__(self,bot:commands.Bot)->None:
        self.bot = bot
        self.data = self.loadData()

    @app_commands.command(name='cweapon', description='Display info about a Cycle weapon')
    #@app_commands.guilds(discord.Object(817238795966611466))
    async def coinflip(self, interaction:discord.Interaction, weapon:str):
        closest_weapon = difflib.get_close_matches(weapon, self.data['weaponDamage'], n=1, cutoff=0.3)[0]
        data = self.data['weaponDamage'][closest_weapon]
        embed = discord.Embed(title=f'{closest_weapon}', color=0xf5a742)
        embed.set_thumbnail(url=data['Image'])
        embed.add_field(name='Base Dmg',value=data['Damage'], inline=True)
        embed.add_field(name='Pen', value=data['Pen'], inline=True)
        embed.add_field(name='White <:common:985185508151947324>', value=data['Uncommon'], inline=False)
        embed.add_field(name='Green <:uncommon:985185514695041024>', value=data['Common'], inline=False)
        embed.add_field(name='Blue <:rare:985185513185103922>', value=data['Rare'], inline=False)
        embed.add_field(name='Purple <:epic:985185509888360459>', value=data['Epic'], inline=False)
        embed.add_field(name='Red <:exotic:985185511599652905>', value=data['Exotic'], inline=False)
        await interaction.response.send_message(embed=embed)


    def loadData(self)->dict:
        data = {}
        data['weaponDamage'] = self.loadWeaponDamageData()
        #data['weaponRange'] = self.loadWeaponRangeData()
        return data

    def loadWeaponDamageData(self)->dict:
        data = {}
        html = urllib.request.urlopen("https://tcf-info.com/")
        soup = BeautifulSoup(html, 'html.parser')
        tables = soup.find_all('div', {'class':'tab-select'})
        for table in tables:
            body = table.find('tbody')
            for i in range(0,len(body.contents)):
                weapon = {}
                if isinstance(body.contents[i],str):
                    continue
                weapon_data = body.contents[i].contents
                for j in range(0,len(weapon_data)):
                    if not isinstance(weapon_data[j], str):
                        continue
                    if weapon_data[j] == '\n':
                        continue
                    weaponString : str = weapon_data[j]
                    name = weaponString.replace(' ','')
                    if name == 'Image':
                        weapon[name] = BASE_URL + weapon_data[j+2].find('img')['src']
                        continue
                    weapon[name] = weapon_data[j+2].string
                data[weapon['Name']] = weapon
        return data

    def loadWeaponRangeData(self)->dict:
        data = {}

        return data

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Cycle(bot))