import asyncio
import discord,secrets, utility, random, datetime, os
from PIL import Image, ImageDraw, ImageFont
from discord.ext import commands
from discord import Webhook, app_commands
from blackjack_view import BlackjackView
from coinflip_view import CoinflipView

class Casino(commands.Cog):
    def __init__(self,bot:commands.Bot)->None:
        self.bot = bot
        self.activeBJ = []
        self.activeCoinflips = []


    # @app_commands.command(name='',description='')
    # @app_commands.guilds(discord.Object(817238795966611466))
    # async def cc(self, interaction:discord.Interaction, amount : app_commands.Range[float,1,50]):
    #     if not await utility.checkIfUserHasAmount(interaction.user.id, amount):
    #         await interaction.response.send_message("You don't have enough money.")
    #         return
        

    @app_commands.command(name='coinflip', description='Start a coinflip match. Other players can enter this with a +/- 5% money difference.')
    #@app_commands.guilds(discord.Object(817238795966611466))
    async def coinflip(self, interaction:discord.Interaction, amount:app_commands.Range[float,1,50], side:str):
        if not await utility.checkIfUserHasAmount(interaction.user.id, amount):
            await interaction.response.send_message("You don't have enough money.")
            return
        game_data = {'player1':interaction.user, 'player1Side':side, 'bet':amount, 'complete':False}
        await utility.takeMoneyFromId(interaction.user.id, amount)
        self.activeCoinflips.append(game_data)
        embed = self.generateCoinflipStartEmbed(game_data)
        view = CoinflipView(game_data, self)
        await interaction.response.send_message(embed=embed,view=view)
        msg = await interaction.original_message()
        game_data['followupId'] = msg.id
        game_data['followup'] = interaction.followup

    def generateCoinflipStartEmbed(self, game_data):
        embed = discord.Embed(title='Coinflip Game', color=0x242424, timestamp=datetime.datetime.now())
        embed.set_footer(text='Started')
        embed.set_author(name=game_data['player1'].display_name, icon_url=game_data['player1'].display_avatar.url)
        lowerBound = game_data['bet'] * 0.95
        higherBound = game_data['bet'] * 1.05
        game_data['higher'] = higherBound
        game_data['lower'] = lowerBound
        player1Coin = '<:valorantcoin:963660425914880050>' if game_data['player1Side'] == 'valorant' else '<:leaguecoin:963660425872957563>'
        player2Coin = '<:leaguecoin:963660425872957563>' if game_data['player1Side'] == 'valorant' else '<:valorantcoin:963660425914880050>'
        embed.add_field(name=f"{player1Coin} = {game_data['player1'].display_name}", value="\u200b")
        embed.add_field(name=f'\u200b', value='\u200b')
        embed.add_field(name=f'{player2Coin} = ?', value='\u200b')
        embed.add_field(name='Lower', value=f'```yaml\n£{lowerBound:.2f}\n```')
        embed.add_field(name='Pot', value=f"```yaml\n£{game_data['bet']:.2f}\n```")
        embed.add_field(name='Higher', value=f'```yaml\n£{higherBound:.2f}\n```')
        return embed

    def generateCoinflipEmbed(self,game_data):
        embed = discord.Embed(title='Coinflip Starting', color=0x00204f, timestamp=datetime.datetime.now())
        embed.set_footer(text='Beginning soon')
        embed.set_author(name=game_data['player1'].display_name, icon_url=game_data['player1'].display_avatar.url)
        player1Coin = '<:valorantcoin:963660425914880050>' if game_data['player1Side'] == 'valorant' else '<:leaguecoin:963660425872957563>'
        player2Coin = '<:leaguecoin:963660425872957563>' if game_data['player1Side'] == 'valorant' else '<:valorantcoin:963660425914880050>'
        embed.add_field(name=f"{player1Coin} = {game_data['player1'].display_name}", value=f"```yaml\n£{game_data['bet']}\n```")
        embed.add_field(name=f'\u200b', value='\u200b')
        embed.add_field(name=f"{player2Coin} = {game_data['player2'].display_name}", value=f"```yaml\n£{game_data['player2Bet']}\n```")
        return embed

    async def coinflipCallback(self,view,game_data):
        embed = self.generateCoinflipEmbed(game_data)
        view.clear_items()
        await game_data['followup'].edit_message(message_id=game_data['followupId'], embed=embed,view=view)
        await asyncio.sleep(2)
        player1Chance = game_data['bet'] / (game_data['bet'] + game_data['player2Bet'])
        randNum = random.randint(1,10000)
        if 10000 * player1Chance >= randNum:
            winner = game_data['player1']
            winningCoin = 'valorantcoin.gif' if game_data['player1Side'] == 'valorant' else 'leaguecoin.gif' 
        else:
            winner = game_data['player2']
            winningCoin = 'leaguecoin.gif' if game_data['player1Side'] == 'valorant' else 'valorantcoin.gif' 
        gifFile = discord.File(f'localCasinoContent/{winningCoin}')
        followup : Webhook = game_data['followup']
        await followup.edit_message(message_id=game_data['followupId'], attachments=[gifFile] ,embed=embed,view=view)
        await asyncio.sleep(5)
        embed = self.generateCoinflipWonEmbed(game_data, winner)
        game_data['complete'] = True
        jackpot = game_data['bet'] + game_data['player2Bet']
        await utility.sendMoneyToId(winner.id, jackpot)
        loserid = game_data['player1'].id if winner.id == game_data['player2'].id else game_data['player2'].id
        loseramount = game_data['bet'] if winner.id == game_data['player2'].id else game_data['player2Bet']
        await utility.addCoinflipProfit(winner.id, jackpot - loseramount)
        await utility.addCoinflipProfit(loserid,-loseramount)
        await followup.edit_message(message_id=game_data['followupId'], embed=embed, attachments=[])

    def generateCoinflipWonEmbed(self, game_data, winner):
        embed = discord.Embed(title='Coinflip Over', color=0xcf8a13, timestamp=datetime.datetime.now())
        embed.set_footer(text=f'Winner {winner.display_name}')
        embed.set_author(name=game_data['player1'].display_name, icon_url=game_data['player1'].display_avatar.url)
        player1Coin = '<:valorantcoin:963660425914880050>' if game_data['player1Side'] == 'valorant' else '<:leaguecoin:963660425872957563>'
        player2Coin = '<:leaguecoin:963660425872957563>' if game_data['player1Side'] == 'valorant' else '<:valorantcoin:963660425914880050>'
        embed.add_field(name=f"{player1Coin} = {game_data['player1'].display_name}", value="\u200b")
        embed.add_field(name=f'\u200b', value='\u200b')
        embed.add_field(name=f"{player2Coin} = {game_data['player2'].display_name}", value='\u200b')
        pot = game_data['bet'] + game_data['player2Bet']
        embed.add_field(name=f'{winner.display_name} Won £{pot}', value='\u200b',inline=False)
        return embed

    async def coinflipTimeout(self, game_data):
        if not game_data['complete']:
            await utility.sendMoneyToId(game_data['player1'].id, game_data['bet'])
        self.activeCoinflips.remove(game_data)

    @coinflip.autocomplete('side')
    async def coinflip_complete(self, interaction : discord.Interaction, current : str):
        sides = ['valorant','league']
        return[
            app_commands.Choice(name=side, value=side)
            for side in sides if current.lower() in side.lower()
        ]

    @app_commands.command(name='blackjack', description="Start a blackjack game")
    @app_commands.checks.cooldown(12, 600)
    #@app_commands.guilds(discord.Object(817238795966611466))
    async def blackjack(self, interaction:discord.Interaction, amount:app_commands.Range[float,1,50]):
        for x in self.activeBJ:
            if x['discord_id'] == interaction.user.id:
                await interaction.response.send_message("You're already in a Blackjack game.", ephemeral=True)
                return
        if not await utility.checkIfUserHasAmount(interaction.user.id, amount):
            await interaction.response.send_message("You don't have enough money.")
            return

        suits = ['diamonds','hearts','spades','clubs']
        deck = {}
        for i in suits:
            for j in range(1,14):
                cardname = f'{i}{j}.png'
                value = min(j,10)
                if j == 1:
                    value = 11
                deck[cardname] = value
        game_data = {'player':{}, 'dealer':{}, 'deck':deck, 'bet':amount, 'discord_id':interaction.user.id, 'discord_icon':interaction.user.avatar.url}
        self.hitHand(game_data['dealer'], deck)
        self.hitHand(game_data['player'], deck)
        self.hitHand(game_data['player'], deck)
        self.activeBJ.append(game_data)
        view = BlackjackView(game_data['discord_id'],self)
        await utility.takeMoneyFromId(game_data['discord_id'], amount)
        await utility.addBlackjackProfit(game_data['discord_id'], -amount)
        embed = await self.generateBlackJackEmbed(game_data)
        await interaction.response.send_message(embed=embed,view=view)

    async def blackjackViewCallback(self,interaction:discord.Interaction, did, label):
        notFound = True
        for x in self.activeBJ:
            if x['discord_id'] == did:
                game_data=x
                notFound = False
                break
        if notFound:
            return
        won = False
        draw = False
        if label == 'Hit':
            self.hitHand(game_data['player'], game_data['deck'])
            if self.getHandValue(game_data['player']) > 21:
                embed = await self.generateBlackJackEmbed(game_data)
                embed.set_author(name='Bust! You lose.')
                embed.set_footer(text=f"You lost £{game_data['bet']}")
                await interaction.response.edit_message(embed=embed)
                self.activeBJ.remove(game_data)
                return
        else:
            self.updateDealer(game_data['dealer'],game_data['deck'], True)
            embed = await self.generateBlackJackEmbed(game_data)
            if self.getHandValue(game_data['dealer']) > 21:
                embed.set_author(name='Dealer Bust! You Win!')
                embed.set_footer(text=f"You won £{game_data['bet']}")
                await interaction.response.edit_message(embed=embed)
                self.activeBJ.remove(game_data)
                won = True
            elif self.getHandValue(game_data['dealer']) > self.getHandValue(game_data['player']):
                embed.set_author(name='Dealer Drew Higher, You Lose.')
                embed.set_footer(text=f"You lost £{game_data['bet']}")
                await interaction.response.edit_message(embed=embed)
                self.activeBJ.remove(game_data)
                return
            elif self.getHandValue(game_data['player']) > self.getHandValue(game_data['dealer']):
                embed.set_author(name='You Drew Higher, You Win!')
                embed.set_footer(text=f"You won £{game_data['bet']}")
                await interaction.response.edit_message(embed=embed)
                self.activeBJ.remove(game_data)
                won = True
            elif len(game_data['dealer']) < len(game_data['player']):
                embed.set_author(name='Dealer Has Less Cards, You Lose.')
                embed.set_footer(text=f"You lost £{game_data['bet']}")
                await interaction.response.edit_message(embed=embed)
                self.activeBJ.remove(game_data)
                return
            elif len(game_data['player']) < len(game_data['dealer']):
                embed.set_author(name='You Have Less Cards, You Win!')
                embed.set_footer(text=f"You won £{game_data['bet']}")
                await interaction.response.edit_message(embed=embed)
                self.activeBJ.remove(game_data)
                won = True
            else:
                embed.set_author(name='Same Number of Cards and Same Value, Dealer Wins.')
                embed.set_footer(text=f"You lost £{game_data['bet']}")
                await interaction.response.edit_message(embed=embed)
                self.activeBJ.remove(game_data)
        if won:
            await utility.sendMoneyToId(game_data['discord_id'], game_data['bet'] * 2)
            await utility.addBlackjackProfit(game_data['discord_id'], game_data['bet'] * 2)
            return
        embed = await self.generateBlackJackEmbed(game_data)
        await interaction.response.edit_message(embed=embed)
        return
        
    async def generateBlackJackEmbed(self,game_data):
        embed= discord.Embed(title='Blackjack', color=0x14a307)
        playerHand = game_data['player']
        dealerHand = game_data['dealer']
        backImage = Image.open('localCasinoContent/board.png')
        draw = ImageDraw.Draw(backImage)
        font = ImageFont.truetype('localValorantContent/Cafe.ttf', 48)
        font2 = ImageFont.truetype('localValorantContent/Cafe.ttf', 24)
        draw.text((60,50), "YOU", (255,255,255), font=font, stroke_width=2, stroke_fill=(0,0,0))
        draw.text((275,50), "DEALER", (255,255,255), font=font, stroke_width=2, stroke_fill=(0,0,0))
        cardCount = 0
        width = 45
        size = 128
        if len(playerHand) > 4:
            diff = len(playerHand) - 4
            width -= (diff * 7)
            size -= (diff * 8)
        for cardKey in playerHand:
            valueOfHand = self.getHandValue(playerHand)
            card_image = Image.open(f'localCasinoContent/{cardKey}')
            card_image.thumbnail((size,size), Image.ANTIALIAS)
            backImage.paste(card_image, (15 + (cardCount*width), 165), card_image)
            draw.text((100,105), f"{valueOfHand}", (255,255,255), font=font2, stroke_width=1, stroke_fill=(0,0,0))
            cardCount+=1
        cardCount = 0
        size = 128
        width = 45
        if len(dealerHand) > 4:
            diff = len(dealerHand) - 4
            width -= (diff * 7)
            size -= (diff * 8)
        for cardKey in dealerHand:
            valueOfHand = self.getHandValue(dealerHand)
            card_image = Image.open(f'localCasinoContent/{cardKey}')
            card_image.thumbnail((size,size), Image.ANTIALIAS)
            backImage.paste(card_image, (260 + (cardCount*width), 165), card_image)
            draw.text((345,105), f"{valueOfHand}", (255,255,255), font=font2, stroke_width=1, stroke_fill=(0,0,0))
            cardCount+=1
        filepath = f"{datetime.datetime.now().strftime('%H-%M-%S')}{game_data['discord_id']}.png"
        backImage.save(filepath)
        file = discord.File(filepath, filename='board.png')
        vKChannel = self.bot.get_channel(os.getenv('valImageChannel'))
        img_msg = await vKChannel.send(file=file)
        embed.set_image(url=img_msg.attachments[0].url)
        os.remove(filepath)
        return embed

    def getHandValue(self,hand:dict):
        sum = 0
        aces = 0
        for key,value in hand.items():
            sum += value
            if value == 11:
                aces += 1
            if sum > 21:
                if aces > 0:
                    aces-=1
                    sum -= 10
        return sum

    def updateDealer(self, hand,deck, drawTil17):
        while self.getHandValue(hand) < 17:
            self.hitHand(hand,deck)
        return

    def hitHand(self, hand:list, deck:dict):
        card,value = random.choice(list(deck.items()))
        deck.pop(card)
        hand[card]=value

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Casino(bot))
