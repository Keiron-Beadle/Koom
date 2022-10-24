import discord, asyncio, youtube_dl, utility, time, ctypes, ctypes.util
from discord.ext import commands
from discord.ui import Button, View
from random import seed, randint

ydl_opts = {'format':'bestaudio/best','postprocessors': [{'key':'FFmpegExtractAudio','preferredcodec':'mp3','preferredquality':'192'}], 'yes-playlists':True}
ydl = youtube_dl.YoutubeDL(ydl_opts)

class Music(commands.Cog):
    def __init__(self,bot:commands.Bot)->None:
        self.bot = bot
        self.initialiseVariables()
        self.economy = bot.get_cog("Economy")
        find_opus = ctypes.util.find_library('opus')
        discord.opus.load_opus(find_opus)


    def initialiseVariables(self):
        self.queuePointer = 0
        self.queue = []
        self.voiceChannel = None
        self.reachedEnd = False
        self.loop = False
        self.loopQueue = False
        self.ignorePostSongEvent = False
        self.timeout = 0
        self.queueStart = 0
        self.queueEnd = 10

    @commands.Cog.listener()
    async def on_voice_state_update(self,member,before,after):
        if self.bot.application_id == member.id and after.channel == None:
            self.cleanup()
            return
        
        elif self.bot.application_id == member.id and before.channel is None:
            voice = after.channel.guild.voice_client
            time = 0
            while True:
                await asyncio.sleep(1)
                time = time + 1
                if voice.is_playing() and not voice.is_paused():
                    time = 0
                if time == 10:
                    await voice.disconnect()
                if not voice.is_connected():
                    self.cleanup()
                    break

    def cleanup(self):
        self.ignorePostSongEvent = True
        self.initialiseVariables()

    @commands.command()
    async def summon(self,ctx):
        await ctx.author.voice.channel.connect()
        await ctx.guild.change_voice_state(channel=ctx.author.voice.channel, self_deaf=True)

    @commands.command(aliases=['q','queue'])
    async def sendQueue(self,ctx):
        await self.sendQueueList(ctx)
        
    @commands.command(aliases=['loop','l'])
    async def loopSong(self,ctx):
        self.loop = not self.loop
        if self.loop:
            await ctx.send("Current song is now looped.")
            return
        await ctx.send("Current song is now un-looped.")
    
    @commands.command(aliases=['loopqueue','lq'])
    async def loopTheQueue(self,ctx):
        self.loopQueue = not self.loopQueue
        if self.loopQueue:
            await ctx.send("Current queue is now looped.")
            return
        await ctx.send("Current queue is now un-looped.")

    @commands.command(aliases=['dc','disconnect','leave'])
    async def dcChannel(self,ctx):
        if ctx.voice_client.channel != ctx.author.voice.channel:
            await ctx.send("You are not in the same voice channel as Koom.")
            raise commands.CommandError("Author not connected to same voice channel as Koom.")
        await ctx.voice_client.disconnect()
        self.initialiseVariables()

    @commands.command()
    async def skip(self, ctx):
        if self.loop:
            self.loop = not self.loop
        if self.reachedEnd:
            await self.sendEndOfQueue(ctx)           
            return
        ctx.voice_client.stop()      

    @commands.command()
    async def seek(self, ctx, timestamp : str):
        self.ignorePostSongEvent = True
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
        if timestamp.__contains__(':'):
            parsed = timestamp.split(':')
            if all(isinstance(x,int) for x in parsed):
                await ctx.send("Invalid seek")
                return
            if len(parsed) == 2:                
                s = int(parsed.pop())
                m = int(parsed.pop())
                formatString = "{:01d}:{:02d}".format(m,s)
                seconds = s + m * 60
            elif len(parsed) == 3:
                s = int(parsed.pop())
                m = int(parsed.pop())
                h = int(parsed.pop())
                formatString = "{:01d}:{:02d}:{:02d}".format(h,m,s)
                seconds = s + m * 60 + h * 3600
            else:
                return
        elif str.isdigit(timestamp):
            seconds = int(timestamp)
            m,s = divmod(seconds, 60)
            formatString = "{:02d}:{:02d}".format(m,s)
        else:
            return
        duration = self.queue[self.queuePointer]['duration'].split(':')
        durationSeconds = int(duration[0]) * 60 + int(duration[1])
        if seconds > durationSeconds:
            await ctx.send("Seek beyond the song duration")
            return
        await self.play(ctx, seconds)
        await ctx.send(f"Skipped to {formatString}")
        self.ignorePostSongEvent = False
         
    @commands.command()
    async def shuffle(self, ctx):
        seed(time.time())
        queueLength = len(self.queue)
        iterationCount = randint(queueLength * 2, queueLength * 5)
        for _ in range(0,iterationCount):
            i1 = randint(1,queueLength-1)
            i2 = randint(1,queueLength-1)
            if i1 == i2:
                continue
            temp = self.queue[i1]
            self.queue[i1] = self.queue[i2]
            self.queue[i2] = temp
        await ctx.send("Shuffled playlist.")

    @commands.command(aliases=['play','p'])
    async def queue_song(self, ctx, *input : str):
        arg = ' '.join(input)
        if len(arg) == 0:
            #self.decrementPointer()
            await self.play(ctx,0)
            return
        if self.is_url(arg):
            info = ydl.extract_info(arg, download=False)
        else:
            info = ydl.extract_info(f"ytsearch:{arg}", download=False)['entries'][0]
        duration = utility.secondsToMinSecString(int(info['duration']))
        data = {
            'title' : info['title'],
            'hostURL' : info['url'],
            'webpage_url' : info['webpage_url'],
            'duration' : duration,
            'thumbnail': info['thumbnails'][3]['url'],
            'author' : ctx.message.author.display_name }
        self.queue.append(data)
        if ctx.voice_client is not None and ctx.voice_client.is_playing():
            await self.sendSuccessQueue(ctx, data)
        if self.reachedEnd:
            self.queuePointer+=1
            self.reachedEnd = False
        await self.tryPlay(ctx)

    async def tryPlay(self,ctx):
        if ctx.voice_client.is_playing():
            return
        await self.play(ctx)

    async def play(self, ctx, seek = 0):
        FFMPEG_OPT =  {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
        try:
            url = self.queue[self.queuePointer]['hostURL']
            stream = discord.FFmpegPCMAudio(url, **FFMPEG_OPT)
            totalTime = 0
            if isinstance(seek,int) and seek > 0:
                async with ctx.typing():
                    while totalTime < seek:
                        stream.read()
                        totalTime += 0.02
            ctx.voice_client.play(stream, after=lambda e: asyncio.run_coroutine_threadsafe(self.post_song(ctx), self.bot.loop))
            if not self.loop:
                await self.sendPlayingMessage(ctx)
        except Exception as e:
            print(e)            

    async def post_song(self, ctx):
        if self.ignorePostSongEvent:
            return
        if self.loop:
           await self.play(ctx)
           return
        self.incrementPointer()
        if not self.reachedEnd:
            await self.play(ctx)
            return
        if ctx.voice_client is not None:
            await self.sendEndOfQueue(ctx)

    def incrementPointer(self):
        if self.loopQueue:
            if self.queuePointer >= len(self.queue)-1:
                self.queuePointer = 0
                self.reachedEnd = False
                return
        if self.queuePointer >= len(self.queue)-1:
            self.reachedEnd = True
            return
        self.reachedEnd = False
        self.queuePointer = self.queuePointer + 1

    def decrementPointer(self):
        if (self.loop or self.loopQueue) and self.queuePointer == 0:
            self.queuePointer = len(self.queue)-1
            return
        self.queuePointer = self.queuePointer - 1
        self.reachedEnd = False

    def is_url(self, argument:str):
        return argument.startswith("http")

    ####### COROUTINES ############

    @seek.before_invoke
    @skip.before_invoke
    async def ensure_song_playing(self,ctx):
        if ctx.voice_client is None:
            await ctx.send("Song is not playing.")
            raise commands.CommandError("Song is not currently playing - No Voice Client.")
        if ctx.voice_client.channel != ctx.author.voice.channel:
            await ctx.send("You are not in the same voice channel as Koom.")
            raise commands.CommandError("Author not connected to same voice channel as Koom.")        
        if ctx.voice_client.is_playing():
            return
        await ctx.send("Song is not playing.")
        raise commands.CommandError("Song is not currently playing.")

    @summon.before_invoke
    async def ensure_not_connected(self,ctx):
        if ctx.voice_client is None:
            return
        await ctx.send("Koom is already connected to a channel")
        raise commands.CommandError("Koom is already connected to a chat.")

    @loopTheQueue.before_invoke
    @loopSong.before_invoke
    @shuffle.before_invoke
    async def ensure_author_same_vc(self,ctx):
        if ctx.voice_client is None:
            await self.ensure_voice_connect(ctx)
        if ctx.author.voice.channel is None or ctx.voice_client.channel != ctx.author.voice.channel:
            await ctx.send("You are not in the same voice channel as Koom.")
            raise commands.CommandError("Author not connected to same voice channel as Koom.")

    @queue_song.before_invoke
    async def ensure_voice_connect(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
                await ctx.guild.change_voice_state(channel=ctx.author.voice.channel, self_deaf=True)
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")
        return

    ###############################
     
    ######## OUTPUT ########
    async def sendEndOfQueue(self,ctx):
        await ctx.send("End of queue.")

    async def sendSuccessQueue(self,ctx,data):
        embed = discord.Embed(title="Queued Song", color=0x37a7db)
        truncated = data['title']
        if len(truncated) > 27:
            truncated = truncated[0:26] + '...'
        embed.add_field(name="Song Name", value=truncated, inline=False)
        embed.add_field(name="Duration", value=data['duration'], inline=False)
        embed.set_footer(text=f"Requested by {data['author']}")
        await ctx.send(content=data['webpage_url'],embed=embed)

    async def sendPlayingMessage(self,ctx):
        data = self.queue[self.queuePointer]
        embed = discord.Embed(title="Now Playing", color=0x26d437)
        truncated = data['title']
        if len(truncated) > 27:
            truncated = truncated[0:26] + '...'
        embed.add_field(name="Song Name", value=truncated, inline=False)
        embed.add_field(name="Duration", value=data['duration'], inline=False)
        embed.set_footer(text=f"Requested by {data['author']}")
        await ctx.send(content=data['webpage_url'],embed=embed)

    async def sendQueueList(self,ctx):
        view = View(timeout=120.0)
        leftBtn = utility.QueueButton(pStyle=discord.ButtonStyle.grey, pEmoji='⬅️',musicCog=self, author=ctx.author)
        rightBtn = utility.QueueButton(pStyle=discord.ButtonStyle.grey, pEmoji='➡️', musicCog=self, author=ctx.author)
        leftBtn.disabled = True
        if len(self.queue) <= 10:
            rightBtn.disabled = True
        view.add_item(leftBtn).add_item(rightBtn)
        embed = utility.generateQueueEmbed(self, ctx.author)
        await ctx.send(embed=embed, view=view)

    ###############################

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Music(bot))
