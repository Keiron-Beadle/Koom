from datetime import datetime
import discord, secrets
from discord.ext import commands
from discord import app_commands

class Base(commands.Cog):
    def __init__(self,bot:commands.Bot)->None:
        self.bot = bot
    
    @commands.command()
    async def load(self,ctx, cog):
        if ctx.author.id != secrets.keironID:
            return
        await self.bot.load_extension(f'cogs.{cog}')
        await ctx.send(f"Loaded {cog}")

    @commands.command()
    async def sendvideo(self, ctx,filename:str):
        if ctx.author.id != secrets.keironID:
            return
        file = discord.File(fp=filename)
        await ctx.send(file=file)

    @commands.command()
    async def unload(self, ctx, cog):
        if ctx.author.id != secrets.keironID:
            return
        if cog == 'base':
            await ctx.send("Can't unload the base cog")
            return
        await self.bot.unload_extension(f'cogs.{cog}')
        await ctx.send(f"Unloaded {cog}")

    @commands.command()
    async def begin(self, ctx):
        guild : discord.Guild = ctx.guild
        channel = await guild.fetch_channel(623264928937279499)
        counter = 0
        async for message in channel.history(limit=None):
            #if message.author.id == 496369962311614464:
            counter +=1
            with open('raw.txt','a', encoding='utf-8') as f:
                f.write(message.content + "\n")
        print(f"Messages Scraped: {counter}")

    @app_commands.command(name='patchnote',description="Sends a patch note to the specified channel")
    @app_commands.guilds(discord.Object(817238795966611466))
    async def patchnote(self, interaction:discord.Interaction, channelid:str, title:str, content:str)->None:
        channelid = int(channelid)
        if interaction.user.id != secrets.keironID:
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