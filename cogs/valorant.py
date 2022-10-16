import json, datetime, os
from re import U
import discord,secrets, utility, urllib.request, urllib.parse, hashlib
from PIL import Image, ImageFont, ImageDraw
from typing import List
from utility import *
from riotwatcher import ValWatcher, RiotWatcher
from discord.ext import commands
from discord import app_commands
from valorant_view import ValorantMatchView

MONEY_PER_KILL = 1.1
MONEY_PER_ASSIST = 0.5
MONEY_PER_PLANT = 1.0
MONEY_PER_DEFUSE = 1.0
MONEY_PER_ACE = 30
SPIKE_MULTIPLIER = 0.3
UNRATED_MULTIPLIER = 1.0
COMP_MULTIPLIER = 1.5

class Valorant(commands.Cog):
    def __init__(self,bot:commands.Bot)->None:
        self.bot = bot 
        self.riotwatcher = RiotWatcher(secrets.valKey)
        self.watcher = ValWatcher(secrets.valKey)
        self.activeMatches = []
        self.playerCardUrl = 'https://media.valorant-api.com/playercards/'
        self.agentImageUrl = 'https://media.valorant-api.com/agents/'
        self.compTiers = {0:'Unranked',3:'Iron I',4:'Iron II',5:'Iron III',6:'Bronze I',7:'Bronze II',8:'Bronze III',
        9:'Silver I',10:'Silver II',11:'Silver III',12:'Gold I',13:'Gold II',14:'Gold III',15:'Platinum I',16:'Platinum II',
        17:'Platinum III',18:'Diamond I',19:'Diamond II',20:'Diamond III',21:'Ascendant I',22:'Ascendant II', 23:'Ascendant III', 24:'Immortal I', 25:'Immortal II',
        26:'Immortal III',27:'Radiant'}
        self.initialiseContent()
        self.initialiseMaps()
        with open('localValorantContent/maps.json', 'r', encoding='utf-8') as f:
            self.maps = json.loads(f.readline())
        with open('localValorantContent/gamemodes.json', 'r', encoding='utf-8') as f:
            self.gamemodes = json.loads(f.readline())['data']
            
    @app_commands.command(name='claimvalorant',description='Claim one of your recent 10 Valorant matches. Spike gains are reduced, deathmatch is disabled.')
    #@app_commands.guilds(discord.Object(817238795966611466))
    async def claimvalorant(self, interaction:discord.Interaction, index:app_commands.Range[int,1,10])->None:
        id = interaction.user.id
        author_name = interaction.user.display_name
        avatar_url = interaction.user.display_avatar.url
        self.ensureUserInDatabase(id)
        if not self.userAuthenticated(id):
            await interaction.response.send_message("You have not been authenticated, use /linkvalorant.")
            return
        #await interaction.response.defer(thinking=True)
        utility.execute('SELECT puuid FROM Valorant WHERE did = %s',(id,))
        puuid = utility.cursor.fetchone()[0]
        matchlist = self.watcher.match.matchlist_by_puuid('EU',puuid)['history'][:10]
        match = self.watcher.match.by_id('EU',matchlist[index-1]['matchId'])
        cursor.execute("SELECT claimed FROM Valorant WHERE did = %s",(id,))
        claimed = cursor.fetchone()[0]
        claimedMatches = claimed.split('`')
        if matchlist[index-1]['matchId'] in claimedMatches:
            await interaction.response.send_message("You've already claimed that match.", ephemeral=True)
            return
        gamemode = match['matchInfo']['gameMode']
        if 'QuickBomb' in gamemode:
            displayUrl = 'https://media.valorant-api.com/gamemodes/57038d6d-49b1-3a74-c5ef-3395d9f23a97/displayicon.png'
        elif 'Bomb' in gamemode:
            displayUrl = 'https://media.valorant-api.com/gamemodes/96bd3920-4f36-d026-2b28-c683eb0bcac5/displayicon.png'
        queue = match['matchInfo']['queueId']
        validQueues = ['unrated', 'competitive','spikerush']
        if queue not in validQueues:
            await interaction.response.send_message("You can't claim a deathmatch or special game mode.", ephemeral=True)
            return
        if queue == 'unrated':
            multiplier = UNRATED_MULTIPLIER
        elif queue == 'competitive':
            multiplier = COMP_MULTIPLIER
        elif queue == 'spikerush':
            multiplier = SPIKE_MULTIPLIER
        data = self.getPlayerDataFromMatch(match,puuid)['stats']
        kills = data['kills']
        assists = data['assists']
        missingData = self.getUserPlantsDefusesAces(match, puuid)
        plants = missingData[0]
        defuses = missingData[1]
        aces = missingData[2]
        killMoney = kills * MONEY_PER_KILL * multiplier
        assistMoney = assists * MONEY_PER_ASSIST * multiplier
        plantMoney = plants *MONEY_PER_PLANT * multiplier
        defuseMoney = defuses * MONEY_PER_DEFUSE * multiplier
        aceMoney = aces * MONEY_PER_ACE * multiplier
        sum = killMoney + assistMoney + plantMoney + defuseMoney + aceMoney
        embed = discord.Embed(title='Claimed £{:.02f} from {} Game'.format(sum,queue.title()), color=0x08d427, description=f"Multiplier = {multiplier}x")
        embed.set_author(name=author_name,icon_url=avatar_url)
        embed.set_thumbnail(url=displayUrl)
        embed.add_field(name='Kill Money', value='```yaml\n{} = £{:.02f}\n```'.format(kills, killMoney))
        embed.add_field(name='Assist Money', value='```yaml\n{} = £{:.02f}\n```'.format(assists, assistMoney))
        embed.add_field(name='\u200b', value='\u200b')
        embed.add_field(name='Plant Money', value='```yaml\n{} = £{:.02f}\n```'.format(plants, plantMoney))
        embed.add_field(name='Defuse Money', value='```yaml\n{} = £{:.02f}\n```'.format(defuses, defuseMoney))
        embed.add_field(name='\u200b', value='\u200b')
        if aceMoney > 0:
            embed.add_field(name='Ace Money', value='```yaml\n{} = £{:.02f}\n```'.format(aces, aceMoney),inline=False)
        await utility.sendMoneyToId(id, float(sum))
        await utility.addValorantProfit(id,float(sum))
        claimedMatches.append(matchlist[index-1]['matchId'])
        claimed = '`'.join(claimedMatches).removeprefix('`')
        utility.execute("UPDATE Valorant SET claimed = %s WHERE did = %s",(claimed,id,))
        utility.commit()
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='valorantmatches',description='View your recent valorant matches.')
    #@app_commands.guilds(discord.Object(817238795966611466))
    async def valorantmatches(self, interaction:discord.Interaction)->None:
        id = interaction.user.id
        author_name = interaction.user.display_name
        avatar_url = interaction.user.display_avatar.url
        self.ensureUserInDatabase(id)
        if not self.userAuthenticated(id):
            await interaction.response.send_message("You have not been authenticated, use /linkvalorant.")
            return
        await interaction.response.defer(thinking=True)
        utility.execute('SELECT * FROM Valorant WHERE did = %s',(id,))
        userdata = utility.cursor.fetchone()
        puuid = userdata[3]
        matchlist = self.watcher.match.matchlist_by_puuid('EU', puuid)['history'][:30]
        match1 = self.watcher.match.by_id('EU',matchlist[0]['matchId'])
        player_card = self.getPlayerCardFromMatch(match1, puuid)
        matches = [match1]
        embed_data = {'id':id, 'start':0, 'end':5, 'matches':matches, 'matchlist':matchlist,
                    'puuid':puuid, 'display_name':author_name, 'display_url':avatar_url, 'playercard':player_card,
                    'matchIndex':0, 'roundIndex':0, 'eventIndex':-1}
        view = ValorantMatchView(embed_data, self)
        embed_data['view'] = view
        embed = self.generateMatchOverview(embed_data)
        self.activeMatches.append(embed_data)
        await interaction.followup.send(embed=embed,view=view)

    @app_commands.command(name='unlinkvalorant',description='Unlink your valorant account from discord.')
    #@app_commands.guilds(discord.Object(817238795966611466))
    async def unlinkvalorant(self, interaction:discord.Interaction)->None:
        id = interaction.user.id
        self.ensureUserInDatabase(id)
        utility.execute("SELECT * FROM Valorant WHERE did = %s",(id,))
        userdata = utility.cursor.fetchone()
        authenticated = userdata[2]
        if authenticated == 0:
            await interaction.response.send_message("You're already un-authenticated.", ephemeral=True)
            return
        userdata[2] = False
        utility.execute("UPDATE Valorant SET authenticated = 0 WHERE did = %s",(id,))
        utility.commit()
        await interaction.response.send_message(content="Your valorant account has been unlinked.", ephemeral=True)

    @app_commands.command(name='linkvalorant',description='Link your valorant account to discord using RSO.')
    #@app_commands.guilds(discord.Object(600696326287785984))
    async def linkvalorant(self, interaction:discord.Interaction)->None:
        id = interaction.user.id
       # id = 241716281961742336
        self.ensureUserInDatabase(id)
        utility.execute("SELECT * FROM Valorant WHERE did = %s",(id,))
        userdata = utility.cursor.fetchone()
        authenticated = userdata[2]
        if authenticated == 1:
            await interaction.response.send_message("You're already authenticated.", ephemeral=True)
            return
        hashed_id = self.getHashedId(id)
        hashed_id = urllib.parse.quote_plus(hashed_id)
        url = f"https://thebestcomputerscientist.co.uk/html/koom-request.html?id={hashed_id}"
        embed = discord.Embed(title="Valorant Authentication", color=0xd62c20, url=url)
        embed.set_footer(text="Do not share the attached link with anyone")
        await interaction.user.send(embed=embed)
        await interaction.response.send_message("You have been DM'd an authentication link. Ask Keiron to switch the server on to listen for your authentication.",ephemeral=True)

    @commands.command(name='pullcontent')
    async def pullcontent(self, ctx):
        if ctx.author.id != secrets.keironID:
            return
        try:
            content = self.watcher.content.contents('EU','en-US')
        except:
            await ctx.send("Content server offline, try later bro")
            return
        self.content = content
        self.loadAbilities()
        self.saveJson('localValorantContent/content.json', self.content)
        await ctx.send("Updated successfully.")

    ######### UTILITY ###################

    def getUserPlantsDefusesAces(self, match, puuid):
        rounds = match['roundResults']
        plants = 0
        defuses = 0
        aces = 0
        for round in rounds:
            if round['bombPlanter'] == puuid:
                plants += 1
            if round['bombDefuser'] == puuid:
                defuses += 1
            if not round['roundCeremony'].__contains__('Ace'):
                continue
            playerStats = round['playerStats']
            for player in playerStats:
                if player['puuid'] == puuid and len(player['kills']) >= 5:    
                    aces+=1
        return (plants,defuses,aces)

    def generateMatchOverview(self, embed_data):
        #0 = did, 1 = start, 2=end,3=matches,4=matchlist,5=puuid,6=author_name,7=avatar_url,8=playercard,9=view, 10 = round
        #Blue always defend first
        gamename = self.getUserName(embed_data['puuid'])
        playercardUrl = self.playerCardUrl + embed_data['playercard'] + '/smallart.png'
        embed = discord.Embed(title=f'Recent Matches <a:vibing:747680206734622740>',color=0x1aba9f)
        playerRank = self.getPlayerRankFromMatch(embed_data['matches'][0],embed_data['puuid'])
        embed.set_author(name=f"{embed_data['display_name']}", icon_url=f"{embed_data['display_url']}")
        #embed.set_thumbnail(url=playercardUrl)
        embed.set_image(url=f"{self.playerCardUrl}{embed_data['playercard']}/wideart.png")
        embed.set_footer(text=f"{gamename} : {playerRank}")
        while len(embed_data['matches']) < embed_data['end']+1:
            matchId = embed_data['matchlist'][len(embed_data['matches'])]
            embed_data['matches'].append(self.watcher.match.by_id('EU',matchId['matchId']))         
        for i in range(embed_data['start'], embed_data['end']+1):
            agent = self.getAgentFromMatch(embed_data['matches'][i], embed_data['puuid'])
            mapName = self.getMapNameFromMatch(embed_data['matches'][i])
            gameLengthStr = self.getMatchLength(embed_data['matches'][i])
            embed.add_field(name=f'{i+1} - {agent}', value=f'```yaml\n{mapName}: {gameLengthStr}\n```')
        return embed

    async def matchViewCallback(self, view : ValorantMatchView, interaction:discord.Interaction, text,emoji):
        embed_data = view.match_embed_data
        if text is not None and emoji is None:
            embed_data['matchIndex'] = int(text) - 1 + embed_data['start']
            match_data = embed_data['matches'][embed_data['matchIndex']]
            embed = await self.generateMatchEmbed(match_data, embed_data['display_name'], 
                    embed_data['display_url'], embed_data['playercard'], embed_data['puuid'])
            view.enableMatch()
            await interaction.response.edit_message(embed=embed, view=view)
            return
        if text.startswith('Prev'):
            if text == 'Prev':
                if embed_data['start'] > 0:
                    embed_data['start'] -= 6
                    embed_data['end'] -= 6
                    embed = self.generateMatchOverview(embed_data)
                    view.enableOverview()
                    await interaction.response.edit_message(embed=embed, view=view)
                return
            elif text.__contains__('Round'):
                if embed_data['roundIndex'] > 0:
                    embed_data['roundIndex'] -=1
                    embed_data['eventIndex'] = -1
                    embed = await  self.generateRoundEmbed(embed_data)
                    view.enableRound()
                    await interaction.response.edit_message(embed=embed, view=view)
                return
            elif text.__contains__('Event'):
                if embed_data['eventIndex'] > -1:
                    embed_data['eventIndex'] -=1
                    embed= await self.generateRoundEmbed(embed_data)
                    view.enableRound()
                    await interaction.response.edit_message(embed=embed,view=view)
        elif text.startswith('Next'):
            if text =='Next':
                if (embed_data['end'] < len(embed_data['matchlist'])-1):
                    embed_data['end'] +=6
                    embed_data['start'] +=6
                    embed = self.generateMatchOverview(embed_data)
                    view.enableOverview()
                    await interaction.response.edit_message(embed=embed,view=view)
                return
            elif text.__contains__('Round'):
                maxRoundNum = len(self.getMatchRounds(embed_data['matches'][embed_data['matchIndex']]))
                if embed_data['roundIndex'] <= maxRoundNum-1:
                    view.enableRound()
                    embed_data['eventIndex'] = -1
                    embed_data['roundIndex'] +=1
                    embed = await self.generateRoundEmbed(embed_data)
                    await interaction.response.edit_message(embed=embed, view=view)
                return
            elif text.__contains__('Event'):
                game = embed_data['matches'][embed_data['matchIndex']]
                round = game['roundResults'][embed_data['roundIndex']]
                eventNum = len(self.getEventsInRound(round, game, embed_data['puuid']))
                if embed_data['eventIndex'] < eventNum-1:
                    embed_data['eventIndex'] +=1
                    embed= await self.generateRoundEmbed(embed_data)
                    view.enableRound()
                    await interaction.response.edit_message(embed=embed,view=view)
                return
        embed_data['eventIndex'] = 0
        embed_data['roundIndex'] = 0
        view.enableOverview()
        embed = self.generateMatchOverview(view.match_embed_data)
        await interaction.response.edit_message(embed=embed,view=view)

    async def generateRoundEmbed(self, embed_data):
        game = embed_data['matches'][embed_data['matchIndex']]
        round = game['roundResults'][embed_data['roundIndex']]
        eventIndex = embed_data['eventIndex']
        if eventIndex == -1:
            return self.generateRoundOverview(round, embed_data, game, embed_data['puuid']) 
        return await self.generateEventEmbed(round, embed_data, game, embed_data['puuid'])

    async def generateEventEmbed(self, round, embed_data, match, puuid):
        eventList = self.getEventsInRound(round, match, puuid)
        event = eventList[embed_data['eventIndex']]
        eventNumberString = f"{embed_data['eventIndex']+1}/{len(eventList)}" 
        if event[0] == 'kill':
            return await self.generateKillEmbed(match, event, eventNumberString, puuid)
        elif event[0] == 'bombplanted':
            return await self.generatePlantEmbed(match, event, eventNumberString, puuid)
        else:
            return await self.generateDefuseEmbed(match, event, eventNumberString, puuid)
           
    def generateBombImage(self, match, event,puuid):
        mapId = self.getMapIdFromAssetPath(match['matchInfo']['mapId']).lower()
        for map in self.maps:
            if map['uuid'].upper() == mapId.upper():
                mapData = map
                break
        backImage = Image.open(f'localValorantContent/minimaps/{mapId}.png')
        draw = ImageDraw.Draw(backImage)
        playerTeam = self.getPlayerTeamFromMatch(match,puuid)
        spikeX = event[5]['y'] * mapData['xMultiplier'] + mapData['xScalarToAdd']
        spikeY = event[5]['x'] * mapData['yMultiplier'] + mapData['yScalarToAdd']
        spikeX *= backImage.width
        spikeY *= backImage.height
        font = ImageFont.truetype("localValorantContent/ValorantFont.ttf",30)
        draw.text((spikeX-15,spikeY-15), "B", (229,255,0), font=font, stroke_fill=(0,0,0),stroke_width=1)
        for player in event[4]:
            if self.getPlayerTeamFromMatch(match,player['puuid']) == playerTeam:
                colour = (67,213,230)
            else:
                colour = (227,39,42)
            x = player['location']['y'] * mapData['xMultiplier'] + mapData['xScalarToAdd']
            y = player['location']['x'] * mapData['yMultiplier'] + mapData['yScalarToAdd']
            x *= backImage.width
            y *= backImage.height
            #draw.ellipse((0,0,50,50), fill=colour, outline=(0,0,0))
            draw.ellipse((x-10,y-10,x+10,y+10), fill=colour, outline=(0,0,0))
        file = f"{datetime.datetime.now().strftime('%H-%M-%S')}minimap.png"
        backImage.save(file)
        return file

    def generateKillEventImage(self, match, event, puuid):
        mapId = self.getMapIdFromAssetPath(match['matchInfo']['mapId']).lower()
        for map in self.maps:
            if map['uuid'].upper() == mapId.upper():
                mapData = map
                break
        backImage = Image.open(f'localValorantContent/minimaps/{mapId}.png')
        draw = ImageDraw.Draw(backImage)
        playerTeam = self.getPlayerTeamFromMatch(match,puuid)
        victimX = event[6]['y'] * mapData['xMultiplier'] + mapData['xScalarToAdd']
        victimY = event[6]['x'] * mapData['yMultiplier'] + mapData['yScalarToAdd']
        victimX *= backImage.width
        victimY *= backImage.height
        font = ImageFont.truetype("localValorantContent/ValorantFont.ttf",30)
        draw.text((victimX-15,victimY-15), "X", (195,0,255), font=font, stroke_fill=(0,0,0),stroke_width=1)
        for player in event[5]:
            if self.getPlayerTeamFromMatch(match,player['puuid']) == playerTeam:
                colour = (67,213,230)
                if player['puuid'] == event[7]:
                    colour = (8,0,255)
            else:
                colour = (227,39,42)
                if player['puuid'] == event[7]:
                    colour = (242,88,27)
            x = player['location']['y'] * mapData['xMultiplier'] + mapData['xScalarToAdd']
            y = player['location']['x'] * mapData['yMultiplier'] + mapData['yScalarToAdd']
            x *= backImage.width
            y *= backImage.height
            #draw.ellipse((0,0,50,50), fill=colour, outline=(0,0,0))
            draw.ellipse((x-10,y-10,x+10,y+10), fill=colour, outline=(0,0,0))
        file = f"{datetime.datetime.now().strftime('%H-%M-%S')}minimap.png"
        backImage.save(file)
        return file

    def getEventsInRound(self, round,match, puuid):
        events = []
        playerTeam = self.getPlayerTeamFromMatch(match,puuid)
        teamData = self.getTeamData(match['players'], playerTeam)
        if round['bombPlanter'] is not None:
            planterId = round['bombPlanter']
            charName = self.getAgentOrNameBasedOnInTeam(match,teamData, planterId)
            events.append(('bombplanted', round['plantRoundTime'], round['bombPlanter'],charName, round['plantPlayerLocations'], round['plantLocation']))
        if round['bombDefuser'] is not None:
            defuserId = round['bombDefuser']
            charName = self.getAgentOrNameBasedOnInTeam(match,teamData, defuserId)
            events.append(('bombdefused', round['defuseRoundTime'], round['bombDefuser'],charName,round['defusePlayerLocations'],round['defuseLocation']))
        for player in round['playerStats']:
            for kill in player['kills']:
                killerId = kill['killer']
                victimId = kill['victim']
                killerCharName = self.getAgentOrNameBasedOnInTeam(match,teamData, killerId)
                victimCharName = self.getAgentOrNameBasedOnInTeam(match,teamData, victimId)
                item = self.getWeaponNameFromID(kill['finishingDamage']['damageItem'])
                if kill['finishingDamage']['damageType'] == 'Bomb':
                    continue
                if item is None:
                    ability = kill['finishingDamage']['damageItem']
                    agentId = self.getAgentFromMatchPUUID(match, killerId)
                    item = self.getAbilityNameFromAgentID(ability, agentId)
                events.append(('kill', kill['timeSinceRoundStartMillis'],killerCharName,victimCharName,item, kill['playerLocations'], kill['victimLocation'], killerId))
        events = sorted(events, key=lambda x:x[1])
        return events      

    def getAbilityNameFromAgentID(self, killerAbility, agentId):
        for x in self.content['characters']:
            if x['id'] == agentId.upper():
                for ability in x['abilities']:
                    if ability['slot'] == killerAbility:
                        return ability['displayName']

    def getAgentFromMatchPUUID(self,match, id):
        for x in match['players']:
            if x['puuid'] == id:
                return x['characterId']

    async def generateKillEmbed(self,match, event, eventNumberString, puuid):
        embed = discord.Embed(title='Kill', color=0x726ce6)
        embed.set_author(name=f'Event {eventNumberString}')
        embed.add_field(name='Killer <:jettWut:687911504766566400>',value=f'```yaml\n{event[2]}\n```', inline=False)
        embed.add_field(name='Victim <:wellplayed:589213968036397057>', value=f'```yaml\n{event[3]}\n```', inline=False)
        embed.add_field(name='<:SansFingerGuns:739592028270362746> Weapon',value=f'```yaml\n{event[4]}\n```')
        timeSinceRoundStart = utility.secondsToMinSecString(int(event[1]/1000))
        embed.add_field(name='Time', value=f'```yaml\n{timeSinceRoundStart}\n```')
        img_filePath = self.generateKillEventImage(match, event, puuid)
        file = discord.File(img_filePath, filename='minimap.png')
        vKChannel = self.bot.get_channel(secrets.valImageChannel)
        img_msg = await vKChannel.send(file=file)
        embed.set_image(url=img_msg.attachments[0].url)
        os.remove(img_filePath)
        return embed

    async def generatePlantEmbed(self,match, event, eventNumberString, puuid):
        embed = discord.Embed(title='Bomb Planted', color=0xff0303)
        embed.set_author(name=f'Event {eventNumberString}')
        embed.add_field(name='Planted By:', value=f'```yaml\n{event[3]}\n```', inline=False)
        timeSinceRoundStart = utility.secondsToMinSecString(int(event[1]/1000))
        embed.add_field(name='Planted At:',value=f'```yaml\n{timeSinceRoundStart}\n```', inline=False)
        img_filePath = self.generateBombImage(match, event, puuid)
        file = discord.File(img_filePath, filename='minimap.png')
        vKChannel = self.bot.get_channel(secrets.valImageChannel)
        img_msg = await vKChannel.send(file=file)
        embed.set_image(url=img_msg.attachments[0].url)
        os.remove(img_filePath)
        return embed

    async def generateDefuseEmbed(self,match,  event, eventNumberString, puuid):
        embed = discord.Embed(title='Bomb Defused', color=0x38ffaf)
        embed.set_author(name=f'Event {eventNumberString}')
        embed.add_field(name='Defused By:', value=f'```yaml\n{event[3]}\n```', inline=False)
        timeSinceRoundStart = utility.secondsToMinSecString(int(event[1]/1000))
        embed.add_field(name='Defused At:',value=f'```yaml\n{timeSinceRoundStart}\n```', inline=False)
        img_filePath = self.generateBombImage(match, event, puuid)
        file = discord.File(img_filePath, filename='minimap.png')
        vKChannel = self.bot.get_channel(secrets.valImageChannel)
        img_msg = await vKChannel.send(file=file)
        embed.set_image(url=img_msg.attachments[0].url)
        os.remove(img_filePath)
        return embed

    def generateRoundOverview(self,round,embed_data, match,puuid):
        if round['roundResult'] == 'Surrendered':
            embed = discord.Embed(title='Surrendered', color=0xffffff)
            embed_data['view'].enableBackOnly()
            return embed 
        roundNum = round['roundNum']
        roundCeremony = round['roundCeremony']
        winningTeam = round['winningTeam']
        playerTeam = self.getPlayerTeamFromMatch(match,puuid)
        otherTeam = 'Red' if playerTeam == 'Blue' else 'Blue'
        match = embed_data['matches'][embed_data['matchIndex']]
        roundWins = self.getWinsAtRound(match,embed_data['roundIndex'], playerTeam)
        roundLosses = self.getWinsAtRound(match,embed_data['roundIndex'], otherTeam)
        if winningTeam == playerTeam:
            won = 'Win'
            color=0x2fc256
        else:
            won = 'Lost'
            color=0xdb4527
        for x in round['playerStats']:
            if x['puuid'] == puuid:
                player = x
        kills = len(player['kills'])
        damage = 0
        for dmg in player['damage']:
            damage += dmg['damage']
        eco = player['economy']
        ecoSpent = eco['spent']
        ecoRemainig = eco['remaining']
        ecoStart = ecoRemainig + ecoSpent
        title = f"{roundNum} - {won} - {roundWins}:{roundLosses}"
        if roundCeremony != 'CeremonyDefault' and roundCeremony != '': 
            title += f" - {roundCeremony.removeprefix('Ceremony')}"
        embed= discord.Embed(title=title,color=color)
        
        embed.set_author(name=embed_data['display_name'],icon_url=embed_data['display_url'])
        embed.add_field(name='Damage', value=f'```yaml\n{damage}\n```')
        embed.add_field(name='Kills', value=f'```yaml\n{kills}\n```')
        embed.add_field(name='\u200b', value='\u200b')
        embed.add_field(name='Start', value=f'```yaml\n${ecoStart}\n```')
        embed.add_field(name='Spent', value=f'```yaml\n${ecoSpent}\n```')
        embed.add_field(name='Remaining', value=f'```yaml\n${ecoRemainig}\n```')
        return embed        

    def getAgentOrNameBasedOnInTeam(self,match,teamdata, id):
        for x in teamdata:
            if x[3] == id:
                return x[0]
        return self.getAgentFromMatch(match, id)

    def getWinsAtRound(self, match, roundIndex, team):
        rounds = match['roundResults']
        teamWins = 0
        for i in range(0,roundIndex):
            round_data = rounds[i]
            if round_data['winningTeam'] == team:
                teamWins += 1
        return teamWins

    def getWeaponNameFromID(self, id):
        for x in self.content['equips']:
            if x['id'] == id:
                return x['name']

    def getAgentNameFromID(self, id):
        for x in self.content['characters']:
            if x['id'].upper() == id.upper():
                return x['name']

    async def generateMatchEmbed(self, match_data, display_name, display_icon, playercard, puuid):
        mapName = self.getMapNameFromMatch(match_data)
        win = self.getMatchResult(match_data, puuid)
        if win:
            color = 0x25c242
        else:
            color = 0xd6392b
        resultString = self.getMatchResultRounds(match_data, puuid)            
        embed = discord.Embed(title=f'{mapName} - {resultString}', color=color)
        embed.set_author(name=display_name, icon_url=display_icon)
        team = self.getPlayerTeamFromMatch(match_data,puuid)
        party = self.getPlayerPartyFromMatch(match_data,puuid)
        playerData = self.getPlayerDataFromMatch(match_data, puuid)
        characterId = playerData['characterId']
        characterUrl = self.agentImageUrl + characterId.lower() + '/displayicon.png'
        embed.set_thumbnail(url=characterUrl)
        kills = self.getPlayerKillsFromMatch(match_data, puuid)
        deaths = self.getPlayerDeathsFromMatch(match_data, puuid)
        assists = self.getPlayerAssistsFromMatch(match_data,puuid)
        favouriteWeapon = self.getFavouriteWeaponFromMatch(match_data,puuid)
        abilityUses = self.getPlayerAbilityUsageFromMatch(match_data, puuid)
        embed.add_field(name='Kills <:POGGERS:461342131584237588>',value=f'```yaml\n{kills}\n```')
        embed.add_field(name='Deaths <:4117_Jett_Angry:963428412532346920>',value=f'```yaml\n{deaths}\n```')
        embed.add_field(name='Assists <:8493sagethumbsup:963428406127657060>',value=f'```yaml\n{assists}\n```')
        embed.add_field(name='Fav. Weapon <:7001cheemsak47gobrr:963428799981166632>',value=f'```yaml\n{favouriteWeapon}\n```',inline=False)
        abilityCodeBlock = f'```yaml\n'
        for key in abilityUses.keys():
            abilityCodeBlock += f'{key} : {abilityUses[key]}\n'
        abilityCodeBlock += '```'
        embed.add_field(name="Ability Usage <:4275valorantpheonixmyeyes:963428401597800479>",value=abilityCodeBlock,inline=False)
        matchImageFile = self.makeMatchImage(match_data, team, party, puuid)
        file = discord.File(matchImageFile, filename='image.png')
        vKChannel = self.bot.get_channel(secrets.valImageChannel)
        img_msg = await vKChannel.send(file=file)
        img_url = img_msg.attachments[0].url
        embed.set_image(url=img_url)
        os.remove(matchImageFile)
        return embed

    def getMatchResultRounds(self, match_data, puuid):
        playerTeam = self.getPlayerTeamFromMatch(match_data, puuid)
        teamData = match_data['teams']
        playerTeamNum : str
        enemyTeamNum : str
        for x in teamData:
            if x['teamId'] == playerTeam:
                playerTeamNum = x['roundsWon']
            else:
                enemyTeamNum = x['roundsWon']
        return f"{playerTeamNum} : {enemyTeamNum}"

    def getTeamData(self, players, teamId):
        team = []
        for x in players:
            if x['teamId'] == teamId:
                for y in self.content['playerTitles']:
                    if y['id'].lower() == x['playerTitle'].lower():
                        title = y['name'].removesuffix('Title')
                        break
                team.append([x['gameName'], x['characterId'].upper(),title, x['puuid']])
        return team

    def makeMatchImage(self, data, team, party, puuid):
        players = data['players']
        redTeam = self.getTeamData(players,'Red')
        blueTeam = self.getTeamData(players,'Blue')
        mapId = data['matchInfo']['mapId'].upper()
        mapId = self.getMapIdFromAssetPath(data['matchInfo']['mapId'])
        backImage = Image.open(f'localValorantContent/mapborders/{mapId}.png')
        charPos = [-70,150]
        if team == 'Blue':
            myTeamText = 'Defense'
            myTeamCol = (29,238,242)
            otherTeamCol = (224,61,43)
            otherTeamText = 'Attack'
        else:
            myTeamText = 'Attack'
            myTeamCol = (224,61,43)
            otherTeamCol = (29,238,242)
            otherTeamText = 'Defense'
        myTeamPos = [10, 10]
        otherTeamPos = [750, 10]
        ##draw text#
        draw = ImageDraw.Draw(backImage)
        font = ImageFont.truetype('localValorantContent/ValorantFont.ttf', 128)
        draw.text(myTeamPos, myTeamText, myTeamCol, font=font, stroke_width=2, stroke_fill=(0,0,0))
        draw.text(otherTeamPos, otherTeamText, otherTeamCol, font=font, stroke_width=2, stroke_fill=(0,0,0))
        ##
        if team == 'Red':
            self.drawMyTeam(backImage, puuid, redTeam, party, charPos)
            charPos[0] += 150
            self.drawOtherTeam(backImage, blueTeam, charPos)
        elif team == 'Blue':
            self.drawMyTeam(backImage,puuid, blueTeam, party, charPos)
            charPos[0] += 150
            self.drawOtherTeam(backImage, redTeam, charPos)
        file = f"{datetime.datetime.now().strftime('%H-%M-%S')}.png"
        backImage.save(file)
        return file
    
    def drawMyTeam(self, image : Image.Image, playerId, team, party, start):
        copy = [start[0], start[1]]
        party_icon = Image.open(f'localValorantContent/partyIcon.png')
        player_icon = Image.open(f'localValorantContent/playerIcon.png')
        thickFont = ImageFont.truetype('localValorantContent/CafeBold.ttf', 15)
        lightFont = ImageFont.truetype('localValorantContent/Cafe.ttf', 14)
        for player in team:
            charId = player[1]
            char_img = Image.open(f'localValorantContent/agentbusts/{charId}.png')
            char_img.thumbnail((256,256), Image.ANTIALIAS)
            image.paste(char_img, (copy[0],copy[1]), char_img)
            copy[0] += 115

        for player in team:
            draw = ImageDraw.Draw(image)
            nameratio = len(player[0]) / 10.0
            titleratio = 10.0 / len(player[1])
            xNamePos = float(start[0] + 115.0 - (22 * nameratio))
            xTitlePos = float(start[0] + 115.0 * titleratio)
            draw.text((xNamePos,start[1]+130), player[0], font=thickFont,stroke_width=1, stroke_fill=(0,0,0))
            #draw.text((xTitlePos,start[1]+150), player[2], font=lightFont, strok_width=1, stroke_fill=(0,0,0))
            for p in party:
                if p == player[3]:
                    party_icon.thumbnail((32,32), Image.ANTIALIAS)
                    image.paste(party_icon, (start[0] + 120,start[1]-35), party_icon)
            if player[3] == playerId:
                player_icon.thumbnail((32,32), Image.ANTIALIAS)
                image.paste(player_icon, (start[0] + 120,start[1]-35), player_icon)

            start[0] += 115
            
    def drawOtherTeam(self, image : Image.Image, team, start):
        for player in team:
            charId = player[1]
            char_img = Image.open(f'localValorantContent/agentbusts/{charId}.png')
            char_img.thumbnail((256,256), Image.ANTIALIAS)
            image.paste(char_img, (start[0],start[1]), char_img)
            start[0] += 115

    def getMatchLength(self, match):
        lengthMs = match['matchInfo']['gameLengthMillis']
        return utility.secondsToMinSecString(int(lengthMs / 1000))

    def removeMatchList(self, embed_data):
        for x in self.activeMatches:
            if x == embed_data:
                self.activeMatches.remove(x)
                return

    def getMatchResult(self, match_data, puuid):
        playerTeam = self.getPlayerTeamFromMatch(match_data, puuid)
        for team in match_data['teams']:
            if team['won']:
                return playerTeam == team['teamId']
        return None

    def getFavouriteWeaponFromMatch(self,match_data,puuid):
        roundData = self.getMatchRounds(match_data)
        weapon_uses = {}
        for round in roundData:
            player_stats = self.getPlayerStatsFromRound(round,puuid)
            weaponId = player_stats['economy']['weapon']
            weaponName = self.weaponIdToName(weaponId)
            if weaponName not in weapon_uses:
                weapon_uses[weaponName] = 1
            else:
                weapon_uses[weaponName] += 1
        return max(weapon_uses, key=weapon_uses.get)

    def weaponIdToName(self, weaponId):
       for x in self.content['equips']:
           if x['id'].upper() == weaponId.upper():
               return x['name']

    def getPlayerStatsFromRound(self, round,puuid):
        stats= round['playerStats']
        for x in stats:
            if x['puuid'] == puuid:
                return x

    def getMatchRounds(self, match_data):
        return match_data['roundResults']

    def getMapIdFromAssetPath(self, map):
        maps = self.content['maps']
        for x in maps:
            if x.get('assetPath') == None:
                continue
            if map == x['assetPath']:
                return x['id']

    def getMapNameFromMatch(self,match):
        maps = self.content['maps']
        for x in maps:
            if x.get('assetPath') == None:
                continue
            if match['matchInfo']['mapId'] == x['assetPath']:
                return x['name']

    def getUserName(self,puuid):
        account = self.riotwatcher.account.by_puuid('EUROPE',puuid)
        return account['gameName'] + '#' + account['tagLine']

    def userAuthenticated(self,id):
        entry = self.ensureUserInDatabase(id)
        return entry[2] == 1

    def getPlayerAbilityUsageFromMatch(self, match,puuid):
        playerData = self.getPlayerDataFromMatch(match,puuid)
        abilityCasts = playerData['stats']['abilityCasts']

        for x in self.content['characters']:
            if x['id'].upper() == playerData['characterId'].upper():
                ability1Name = x['abilities'][0]['displayName'].title()
                ability2Name = x['abilities'][1]['displayName'].title()
                grenadeName = x['abilities'][2]['displayName'].title()
                ultName = x['abilities'][3]['displayName'].title()
                break
        if abilityCasts is None:
            return {ability1Name:0, ability2Name:0, grenadeName:0, ultName:0}
        return {ability1Name:abilityCasts['ability1Casts'], ability2Name:abilityCasts['ability2Casts'],
                grenadeName:abilityCasts['grenadeCasts'], ultName:abilityCasts['ultimateCasts']}
                
    def isPlayerAttackOrDefend(self, match, puuid, round):
        team = self.getPlayerTeamFromMatch(match,puuid)
        if (team == 'Blue' and round < 12) or (team=='Red' and round >= 12):
            return 'Defense'
        return 'Attack'

    def getPlayerTeamFromMatch(self, match,puuid):
        playerdata = self.getPlayerDataFromMatch(match,puuid)
        return playerdata['teamId']

    def getAgentFromMatch(self, match, puuid):
        playerData = self.getPlayerDataFromMatch(match ,puuid)
        characterId = playerData['characterId']
        for x in self.content['characters']:
            if x['id'].lower() == characterId.lower():
                return x['name']

    def getPlayerAssistsFromMatch(self, match,puuid):
        playerData = self.getPlayerDataFromMatch(match,puuid)
        return playerData['stats']['assists']

    def getPlayerDeathsFromMatch(self, match,puuid):
        playerData = self.getPlayerDataFromMatch(match,puuid)
        return playerData['stats']['deaths']

    def getPlayerKillsFromMatch(self, match,puuid):
        playerData = self.getPlayerDataFromMatch(match,puuid)
        return playerData['stats']['kills']
    
    def getPlayerPartyFromMatch(self, match,puuid):
        players = match['players']
        partyId = self.getPlayerDataFromMatch(match,puuid)['partyId']     
        party = []
        for p in players:
            if p['partyId'] == partyId:
                party.append(p['puuid'])
        return party

    def getPlayerTitleFromMatch(self, match,puuid):
        titleId = self.getPlayerDataFromMatch(match,puuid)['playerTitle']     
        for x in self.content['playerTitles']:
            if x['id'].lower() == titleId.lower():
                return x['name'].removesuffix('Title')

    def getPlayerRankFromMatch(self, match, puuid):
        tier = self.getPlayerDataFromMatch(match,puuid)['competitiveTier']
        return self.compTiers[tier]

    def getPlayerCardFromMatch(self, match, puuid):
        return self.getPlayerDataFromMatch(match,puuid)['playerCard']
    
    def getPlayerDataFromMatch(self, match,puuid):
        players = match['players']
        for p in players:
            if p['puuid'] == puuid:
                return p

    def getHashedId(self,id):
        hasher = hashlib.sha256()
        data_bytes = bytes(str(id), 'utf-8')
        hasher.update(data_bytes)
        hashed_id = hasher.digest()
        hashed_id = str(hashed_id)
        return hashed_id

    def checkIfUserLinked(self,id):
        entry = self.ensureUserInDatabase(id)
        if entry is None:
            utility.execute('''INSERT INTO Valorant 
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)''', (id,None,0,None,None,None,None,None,'',))
            return False
        if entry[2] == 1:
            return True
        return False
    
    def ensureUserInDatabase(self,id):
        utility.execute("SELECT * FROM Valorant WHERE did = %s",(id,))
        entry = utility.cursor.fetchone()
        if entry is None:
            utility.execute('''INSERT INTO Valorant 
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)''', (id,None,0,None,None,None,None,None,''))
            utility.commit()
            return [id,None,0,None,None,None,None,None]
        return entry

    def checkContentForAbilities(self):
        if self.content['characters'][0].get('abilities') == None:
            self.loadAbilities()
            self.saveJson('localValorantContent/content.json', self.content)

    def saveJson(self, path, json_dict):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(json.dumps(json_dict))

    def loadAbilities(self):
        url = 'https://valorant-api.com/v1/agents/'
        for x in self.content['characters']:
            id = x['id']
            if id == '36FB82AF-409D-C0ED-4B49-57B1EB08FBD5':
                continue # Null UI Data exists...
            with urllib.request.urlopen(f'{url}{id}') as f:
                data = json.loads(f.read().decode('utf-8'))
            x['abilities'] = data['data']['abilities']

    def initialiseContent(self):
        with open('localValorantContent/content.json', 'r', encoding='utf-8') as f:
            try:
                self.content = json.loads(f.readline())
            except:
                print("Error loading the content. Pull a new copy.")
                return
        self.checkContentForAbilities()

    def initialiseMaps(self):
        mapListUrl = 'https://valorant-api.com/v1/maps'
        localMaps = []
        try:
            with urllib.request.urlopen(mapListUrl) as f:
                remoteMaps = json.loads(f.read().decode('utf-8'))['data']
        except:
            print("Error getting remote maps")
            return
        with open('localValorantContent/maps.json', 'r', encoding='utf-8') as f:
            try:
                localMaps = json.loads(f.readline())        
            except:
                pass
        for x in remoteMaps:
            if x not in localMaps:
                localMaps.append(x)
        with open('localValorantContent/maps.json', 'w', encoding='utf-8') as f:
            f.write(json.dumps(localMaps))

    ##########################################

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Valorant(bot))
