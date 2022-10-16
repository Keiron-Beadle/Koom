import discord, secrets, os
from discord.ext import commands

class KoomBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='bruh ', intents=discord.Intents.all(), application_id=881586576235315220, case_insensitive=True)

    async def on_ready(self):
        print(f"{self.user} has connected to Discord.")
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name='the drip.'))

    async def close(self):
        await super().close()

    async def setup_hook(self):
        for x in os.listdir('./cogs'):
            if x.endswith('.py'):
                await self.load_extension(f'cogs.{x[:-3]}')
                print(f'Loaded: {x[:-3]}')
        #synced = await bot.tree.sync()
        #synced = await bot.tree.sync(guild=discord.Object(548257451510726667))
        #print(synced)

bot = KoomBot()
bot.run(secrets.discordToken)
