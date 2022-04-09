import discord, sqlite3
from discord.ext import commands
from discord.ui import Button

league_content_url = 'https://thebestcomputerscientist.co.uk/league_content/'
database = sqlite3.connect("database.sqlite")
cursor : sqlite3.Cursor = database.cursor()

def secondsToMinSecString(secs) -> str:
    m,s = divmod(secs,60)
    return "{:02d}:{:02d}".format(m,s)

async def ensureUserInEconomy(id):
    entry = await getUserEconomy(id)
    if entry is not None:
        return entry
    cursor.execute(f'''INSERT INTO Economy (did,bank,lastdaily,coinflips,blackjacks,profit_blackjack,profit_coinflip) 
    VALUES({id}, 100, 0, 0, 0, 0, 0)''')
    database.commit()
    return [id,100,0,0,0,0,0]

async def getUserEconomy(id):
    return cursor.execute(f'SELECT * FROM Economy WHERE did IS {id}').fetchone()

async def sendMoneyToId(id,amount):
    await ensureUserInEconomy(id)
    user_data = cursor.execute(f'''SELECT * FROM Economy WHERE did IS {id}''').fetchone()
    newValue = user_data[1] + amount
    cursor.execute(f'''UPDATE Economy SET bank = {newValue} WHERE did IS {id}''')
    database.commit()
    return

def secondsToHHMMSS(secs)->str:
    s = secs
    m,s = divmod(s,60)
    h,m = divmod(m, 60)
    return "{:.2f}:{:.2f}:{:.2f}".format(h,m,s)

def isValidLeagueRegion(region : str):
    noPrefix = region.removeprefix('#').upper()
    regions = ['EUW','BR','EUN','JP','NA','OC','TR','KR']
    if regions.__contains__(noPrefix):
        return True
    return False

def generateValorantSuccessEmbed(text, author,author_icon):
    embed = discord.Embed(title="Success <:GoldDoge:932831358483574794>", color=0x2770cf)
    embed.set_author(name=author, icon_url=author_icon)
    embed.add_field(name='\u200b',value=text)
    return embed

def generateValorantFailedEmbed(text,author,author_icon):
    embed = discord.Embed(title="Failed <:phoenixdab:784327000243961858>", color=0xeb4034)
    embed.set_author(name=author, icon_url=author_icon)
    embed.add_field(name='\u200b',value=text)
    return embed


def generateLeagueSuccessEmbed(text, author,author_icon):
    embed = discord.Embed(title="Success <:league:784319004616949790>", color=0x2770cf)
    embed.set_author(name=author, icon_url=author_icon)
    embed.add_field(name='\u200b',value=text)
    return embed

def generateLeagueFailedEmbed(text, author, author_icon):
    embed = discord.Embed(title="Failed <:what:812713040881385492> ", color=0xeb4034)
    embed.set_author(name=author, icon_url=author_icon)
    embed.add_field(name='\u200b',value=text)
    return embed

def generateSuccessEmbed(text, author, author_icon):
    embed = discord.Embed(title="✅ Success", color=0x34eb5b)
    embed.set_author(name=author, icon_url=author_icon)
    embed.add_field(name='\u200b',value=text)
    return embed

def generateFailedEmbed(text, author, author_icon):
    embed = discord.Embed(title="<:among_us_dead:784255946326671372> Failed", color=0xeb4034)
    embed.set_author(name=author, icon_url=author_icon)
    embed.add_field(name='\u200b',value=text)
    return embed

async def getDisplayNameFromID(bot, id):
    return (await bot.fetch_user(id)).display_name

def generateBalanceEmbed(name, amount):
    embed = discord.Embed(title=f"{name}'s Balance", color=0xebeb34)
    embed.set_footer(text=f'Requested by {name}')
    embed.add_field(name='Balance',value='£{:.2f}'.format(amount))
    return embed

async def generateBalTopEmbed(eco, author, start, end):
    embed = discord.Embed(title="<:StonksCypher:932829442299031582> Top Balances", color=0xede732)
    embed.set_footer(text=f"Requested by {author.display_name}")
    balNames = '\u200b'
    balAmounts = '\u200b'
    for x in range(start,end):
        if len(eco.topBalances) == x:
            break
        name = await getDisplayNameFromID(eco.bot, eco.topBalances[x][0])
        amount = eco.topBalances[x][1]
        if len(name) > 19:
            name = name[0:18] + '...'
        if x == 0:
            balNames += '👑 '
        else:
            balNames += f'{x}. '
        balNames += f'{name}\n'
        balAmounts += '£{:.2f}\n'.format(amount)
    embed.add_field(name='User', value=balNames)
    embed.add_field(name="Balance", value=balAmounts)
    return embed

def generateQueueEmbed(music,author):
    embed = discord.Embed(title="Queue List", color=0xc98847)
    embed.set_footer(text=f"Requested by {author.display_name}")
    songNames = '\u200b'
    songDurations = '\u200b'
    for x in range(music.queueStart, music.queueEnd):
        if len(music.queue) == x:
            break
        truncated = music.queue[x]['title']
        if len(truncated) > 19:
            truncated = truncated[0:18] + '...'
        songNames += f'{x}. ' + truncated + '\n'
        songDurations += music.queue[x]['duration'] + '\n'
    embed.add_field(name="Name", value=songNames)
    embed.add_field(name='\u200b', value='\u200b')
    embed.add_field(name="Length", value=songDurations)
    return embed

class BalTopButton(Button):
    def __init__(self, style=discord.ButtonStyle.grey, emoji=None, ecoCog = None, author = None):
        super().__init__(style=style, emoji=emoji)
        self.economy = ecoCog
        self.author = author
        self.start = ecoCog.balStartIndex
        self.end = ecoCog.balEndIndex
        if self.emoji == '⬅️':
            if self.start == 0:
                self.diabled = True
        elif self.emoji == '➡️':
            if self.end < 10:
                self.disabled = True

    def updateData(self, btn):
        btn.start = self.start
        btn.end = self.end

    async def callback(self,interaction):
        if self.emoji.name == '⬅️': 
            self.start -= 10
            self.end -= 10
        elif self.emoji.name == '➡️':
            self.start += 10
            self.end += 10
        
        children = self.view.children
        for x in children:
            self.updateData(x)
        
        embed = generateBalTopEmbed(self.music, self.author)
        await interaction.response.edit_message(embed=embed,view=self.view) 


class QueueButton(Button):
    def __init__(self, pStyle=discord.ButtonStyle.grey, pEmoji=None, musicCog = None, author = None):
        super().__init__(style=pStyle, emoji=pEmoji)
        self.music = musicCog
        self.author = author
        if self.emoji == '⬅️':
            if self.music.queueStart == 0:
                self.diabled = True
        elif self.emoji == '➡️':
            if self.music.queueEnd < 10:
                self.disabled = True

    def checkButton(self, btn):
        if btn.emoji.name == '⬅️': 
            if self.music.queueStart == 0:
                btn.disabled = True
            else:
                btn.disabled = False
        elif btn.emoji.name == '➡️':
            if self.music.queueEnd >= len(self.music.queue):
                btn.disabled = True
            else:
                btn.disabled = False

    async def callback(self,interaction):
        if self.emoji.name == '⬅️': 
            self.music.queueStart -= 10
            self.music.queueEnd -= 10
        elif self.emoji.name == '➡️':
            self.music.queueStart += 10
            self.music.queueEnd += 10
        
        children = self.view.children
        for x in children:
            self.checkButton(x)
        
        embed = generateQueueEmbed(self.music, self.author)
        await interaction.response.edit_message(embed=embed,view=self.view)