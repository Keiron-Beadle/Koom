from datetime import datetime
import requests, io
import discord, secrets, os
from discord.ext import commands
from discord import TextChannel, app_commands

class Base(commands.Cog):
    def __init__(self,bot:commands.Bot)->None:
        self.bot = bot
    
    @commands.command()
    async def becky_sleep(self, ctx):
        author = ctx.author.id
        if author != os.getenv('keironID'):
            return
        becky = self.bot.get_user(os.getenv('beckyID'))
        guild : discord.Guild = ctx.guild
        becky_member = guild.get_member(becky.id)
        await becky_member.move_to(None)

    @commands.command()
    async def load(self,ctx, cog):
        if ctx.author.id != os.getenv('keironID'):
            return
        await self.bot.load_extension(f'cogs.{cog}')
        await ctx.send(f"Loaded {cog}")

    @commands.command()
    async def sendvideo(self, ctx,filename:str):
        if ctx.author.id != os.getenv('keironID'):
            return
        file = discord.File(fp=filename)
        await ctx.send(file=file)

    @commands.command()
    async def unload(self, ctx, cog):
        if ctx.author.id != os.getenv('keironID'):
            return
        if cog == 'base':
            await ctx.send("Can't unload the base cog")
            return
        await self.bot.unload_extension(f'cogs.{cog}')
        await ctx.send(f"Unloaded {cog}")

    @commands.command()
    async def decode(self,ctx, num : int):
        await ctx.message.delete()
        message_ref = ctx.message.reference
        if message_ref is None:
            await ctx.send("You didn't reply to a message.")
            return
        message = await ctx.channel.fetch_message(message_ref.message_id)
        if len(message.attachments) == 0:
            await ctx.send("The message you replied to didn't have any files.")
            return
        attachment = message.attachments[0]
        if attachment.content_type != 'image/jpeg' and attachment.content_type != 'image/png':
            await ctx.send("The attachment in the replied message was not a .jpg or .png")
            return
        url = attachment.url
        img_data = requests.get(url).content
        byte_data = bytearray(img_data)
        for index,values in enumerate(img_data):
            byte_data[index] = values ^ int(num)
        io_data = io.BytesIO(byte_data)
        await ctx.author.send(file=discord.File(fp=io_data, filename='temp.png'))

    @commands.command()
    async def begin(self, ctx):
        reject = ['mudae-spam','bot-spam', 'bot-games','mudae', 'mudae-anarchy','drinking-games','bot-help','art','art-resources','weekly-riddles-and-puzzles','weekly-talk','blakebongo-bot']
        guild : discord.Guild = ctx.guild
        channels = await guild.fetch_channels()
        with open('raw.txt','a', encoding='utf-8') as f:
            for channel in channels:
                if not isinstance(channel,TextChannel) or channel.name in reject: continue
                counter = 0
                async for message in channel.history(limit=None):
                    if message.author.bot or len(message.content) < 8 or message.content.startswith('http'):
                        continue
                    #if message.author.display_name == 'Nissa':
                    #    counter +=1
                    f.write(message.content.removesuffix('\n') + "\n")
                print(f"Messages Scraped: {counter}, From: {channel.name}")

    @app_commands.command(name='patchnote',description="Sends a patch note to the specified channel")
    @app_commands.guilds(discord.Object(817238795966611466))
    async def patchnote(self, interaction:discord.Interaction, channelid:str, title:str, content:str)->None:
        channelid = int(channelid)
        if interaction.user.id != os.getenv('keironID'):
            return
        embed = discord.Embed(title=f'{title}',timestamp=datetime.now(), color=0x1076eb)
        content = content.replace('\\n', '\n')
        body = f'```\n{content}\n```'
        embed.add_field(name='\u200b', value=body,inline=False)
        channel = self.bot.get_channel(channelid)
        if channel is None:
            print("Channel was None")
            return
        await channel.send(embed=embed)
        await interaction.response.send_message(content='sent')

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Base(bot))