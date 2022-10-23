import discord, secrets, time,random, utility, sqlite3
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View

#MONEY FOR MODAL TO PLAY VIDEO IN CHANNEL USER AT IN X TIME? 

class Economy(commands.Cog):
    def __init__(self,bot:commands.Bot)->None:
        self.bot = bot
        self.balStartIndex = 0
        self.balEndIndex = 10
        self.topBalances = []

    @app_commands.command(name='bal', description='Print your balance')
    #@app_commands.guilds(discord.Object(817238795966611466))
    async def bal(self, interaction:discord.Interaction)->None:
        id = interaction.user.id
        display_name = interaction.user.display_name
        balance = await utility.ensureUserInEconomy(id)
        embed = utility.generateBalanceEmbed(display_name,balance)
        await interaction.response.send_message(embed=embed)


    @app_commands.command(name="baltop", description="Print up to the top 100 balances")
    #@app_commands.guilds(discord.Object(817238795966611466))
    async def baltop(self, interaction:discord.Interaction)->None:
        await interaction.response.defer(thinking=True)
        view = View(timeout=120.0)
        utility.execute('SELECT * FROM Economy ORDER BY bank DESC')
        self.topBalances = utility.cursor.fetchall()
        embed = await utility.generateBalTopEmbed(self, interaction.user, 0,10)
        leftBtn = utility.BalTopButton(style=discord.ButtonStyle.grey, emoji='⬅️', ecoCog=self, author=interaction.user)
        rightBtn = utility.BalTopButton(style=discord.ButtonStyle.grey, emoji='➡️', ecoCog=self, author=interaction.user)
        leftBtn.disabled = True
        if len(self.topBalances) <= 10:
            rightBtn.disabled = True
        view.add_item(leftBtn).add_item(rightBtn)
        await interaction.followup.send(embed=embed,view=view)
        
    @app_commands.command(name="daily",description="Get your daily reward!")
    #@app_commands.guilds(discord.Object(817238795966611466))
    async def daily(self, interaction:discord.Interaction)->None:
        discord_id = interaction.user.id
        entry = await utility.ensureUserInEconomy(interaction.user.id)
        author_display = interaction.user.display_name
        author_icon = interaction.user.display_avatar.url
        claimStatus = await self.dailyAlreadyClaimed(discord_id)
        if (not claimStatus[0]):
            embed = utility.generateFailedEmbed(f"You have already claimed today. Try again in {claimStatus[1]}", author_display, author_icon)
            await interaction.response.send_message(embed=embed)
            return
        amount = random.randrange(25,50)
        ##user_data = utility.execute(f'SELECT * FROM Economy WHERE did = {discord_id}').fetchone()
        utility.execute(f'UPDATE Economy SET lastdaily = {time.time()} WHERE did = {discord_id}')
        await self.sendMoneyToId(discord_id, amount)
        embed = utility.generateSuccessEmbed(f"You have received £{amount}", author_display,author_icon)
        await interaction.response.send_message(embed=embed)
        utility.commit()

    @app_commands.command(name="pay",description="Pay someone")
    #@app_commands.guilds(discord.Object(817238795966611466))
    async def pay(self,interaction:discord.Interaction,user:discord.User,amount:float)->None:
        author_display = interaction.user.display_name
        author_icon = interaction.user.display_avatar.url
        if amount < 0:
            embed = utility.generateFailedEmbed("Can't send negative money.", author_display, author_icon)
            await interaction.response.send_message(embed=embed)
            return
        hasMoney = await self.checkBalanceForAmount(interaction.user.id, amount)
        if not hasMoney:
            embed = utility.generateFailedEmbed(f"You don't have enough money to do this.", author_display, author_icon)
            await interaction.response.send_message(embed=embed)
            return
        await self.takeMoneyFromId(interaction.user.id, amount)
        await self.sendMoneyToId(user.id, amount)
        embed = utility.generateSuccessEmbed("You have paid **£{:.2f}** to **{}**".format(amount, user.display_name), author_display, author_icon)
        await interaction.response.send_message(embed=embed)
        utility.commit()

    async def dbSendMoneyTo(self, user : discord.User, amount : float):
        utility.execute(f'SELECT * FROM Economy WHERE did = {user.id}')
        result = utility.cursor.fetchone()
        result[1] += amount
        utility.execute(f'UPDATE Economy SET bank = {result[1]} WHERE did = {user.id}')
        #await database.update_one({'_uid':user.id}, {'$inc':{'_currency':amount}})

    ### Utility Economy ###########################

    async def checkBalanceForAmount(self, discord_id, amount : int):
        entry = await utility.ensureUserInEconomy(discord_id)
        if entry[1] >= amount:
            return True
        return False
    
    async def sendMoneyToId(self,id,amount):
        await utility.ensureUserInEconomy(id)
        utility.execute(f'''SELECT * FROM Economy WHERE did = {id}''')
        user_data = utility.cursor.fetchone()
        newValue = user_data[1] + amount
        return utility.execute(f'''UPDATE Economy SET bank = {newValue} WHERE did = {id}''')

    async def takeMoneyFromId(self,id,amount):
        utility.execute(f'SELECT * FROM Economy WHERE did = {id}')
        user_data = utility.cursor.fetchone()
        newValue = user_data[1] - amount
        return utility.execute(f'UPDATE Economy SET bank = {newValue} WHERE did = {id}')
        
    async def dailyAlreadyClaimed(self, id):
        entry = await utility.getUserEconomy(id)
        now = time.time()
        if entry[2] + 86400 < now:
            return [True]

        formatString = utility.secondsToHHMMSS(int((entry[2] - now) + 86400))
        return [False, formatString]    
    #### ### ## ### # ## ##

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Economy(bot))