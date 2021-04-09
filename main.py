import re
import asyncpraw
import discord
import sqlite3
import asyncio
import time
import json
from discord.utils import get
from discord.ext import commands
from asyncprawcore.exceptions import RequestException, ServerError
from random import choice
from os import path
import config

# Allow for bot to get members by id in order to assign roles
intents = discord.Intents.default()
intents.members = True

# Initialize bot instance
client = commands.Bot(command_prefix=config.command_prefix, intents=intents)

# Initialize reddit instance
reddit = asyncpraw.Reddit(client_id=config.reddit_client,
                          client_secret=config.reddit_secret,
                          user_agent=config.reddit_user_agent)

# Initialize sql connection and cursor
conn = sqlite3.connect('botdata.db')
cursor = conn.cursor()


# Function to retrieve xp by user and guild id
def get_xp(guild_id, user_id):
    cursor.execute("SELECT exp FROM experiencelevels WHERE guildid=:guildid AND userid=:userid",
                   {'guildid': guild_id, 'userid': user_id})
    ret_exp = cursor.fetchone()
    if ret_exp is None:
        exp = 0
    else:
        exp, = ret_exp
    return exp


# Function to retrieve level by user and guild id
def get_level(guild_id, user_id):
    cursor.execute("SELECT level FROM experiencelevels WHERE guildid=:guildid AND userid=:userid",
                   {'guildid': guild_id, 'userid': user_id})
    ret_level = cursor.fetchone()
    if ret_level is None:
        level = 0
    else:
        level, = ret_level
    return level


# Function to retrieve last time user gained xp by user and guild id
def get_lasttime(guild_id, user_id):
    cursor.execute("SELECT lasttime FROM experiencelevels WHERE guildid=:guildid AND userid=:userid",
                   {'guildid': guild_id, 'userid': user_id})
    ret_lasttime = cursor.fetchone()
    if ret_lasttime is None:
        lasttime = 0
    else:
        lasttime, = ret_lasttime
    return lasttime


# Subreddit uplink task
async def subs_uplink():
    global CONFIG_DATA
    
    while True:
        guilds = []
        channels = []
        for guild in client.guilds:
            if CONFIG_DATA[str(guild.id)]['cfg']['enable_uplink']:
                guilds.append(guild)
                channel = get(guild.text_channels, name=CONFIG_DATA[str(guild.id)]['cfg']['uplink_channel_name'])
                channels.append(channel)
        try:
            subreddits = await reddit.subreddit('+'.join(config.uplink_subreddits))
            async for submission in subreddits.stream.submissions(skip_existing=True):
                for index, channel in enumerate(channels):
                    try:
                        await channel.send(f'New post from reddit, go check it out! {submission.url}')
                    except AttributeError:
                        await guilds[index].create_text_channel(CONFIG_DATA[str(guilds[index].id)]['cfg']['uplink_channel_name'])
                        channels[index] = get(guilds[index].text_channels,
                                              name=CONFIG_DATA[str(guilds[index].id)]['cfg']['uplink_channel_name'])
                        await channels[index].send(f'New post from reddit, go check it out! {submission.url}')
        except (asyncio.TimeoutError, RequestException, ServerError):
            continue


# Things to do when the bot comes online
@client.event
async def on_ready():
    global CONFIG_DATA
    
    CONFIG_DATA = dict()
    if path.isfile('configurations.json'):
        with open('configurations.json') as f:
                CONFIG_DATA = json.load(f)
        for guild in client.guilds:
            if str(guild.id) in CONFIG_DATA:
                CONFIG_DATA[str(guild.id)]['info'] = {'guild_name': guild.name}
            else:
                CONFIG_DATA[str(guild.id)] = dict()
                CONFIG_DATA[str(guild.id)]['info'] = {'guild_name': guild.name}
                with open('default.json') as f:
                    CONFIG_DATA[str(guild.id)]['cfg'] = json.load(f)
    else:
        for guild in client.guilds:
            CONFIG_DATA[str(guild.id)] = dict()
            CONFIG_DATA[str(guild.id)]['info'] = {'guild_name': guild.name}
            with open('default.json') as f:
                CONFIG_DATA[str(guild.id)]['cfg'] = json.load(f)
    
    with open('configurations.json', 'w') as f:
        json.dump(CONFIG_DATA, f, indent=2)
    
    await client.change_presence(activity=discord.Activity(type=config.status,
                                                           name=config.status_message))
    print('Bot Active')
    client.loop.create_task(subs_uplink())
    print('Subreddit Uplink Established')


# Things to do when a guild is joined
@client.event
async def on_guild_join(guild):
    global CONFIG_DATA
    
    CONFIG_DATA[str(guild.id)] = dict()
    CONFIG_DATA[str(guild.id)]['info'] = {'guild_name': guild.name}
    with open('default.json') as f:
        CONFIG_DATA[str(guild.id)]['cfg'] = json.load(f)
    
    with open('configurations.json', 'w') as f:
        json.dump(CONFIG_DATA, f, indent=2)


# Things to do whenever there is a message
@client.event
async def on_message(message):
    global CONFIG_DATA
    
    if not message.author.bot:
        message_text = message.content.lower()
        
        for key in CONFIG_DATA[str(message.guild.id)]['cfg']['faq']:
            if re.search(key, message_text):
                faq_response_message = CONFIG_DATA[str(message.guild.id)]['cfg']['faq'][key]
                await message.channel.send(faq_response_message)
        
        for trigger in CONFIG_DATA[str(message.guild.id)]['cfg']['auto_responses']:
            if trigger in message_text:
                message_choice = choice(CONFIG_DATA[str(message.guild.id)]['cfg']['auto_responses'][trigger])
                await message.channel.send(message_choice)
        
        with conn:
            cursor.execute("""CREATE TABLE IF NOT EXISTS experiencelevels (
                        guildid string,
                        userid string,
                        level integer,
                        exp integer,
                        lasttime integer
                        )""")
        
        xp = get_xp(message.guild.id, message.author.id)
        old_level = get_level(message.guild.id, message.author.id)
        lasttime = get_lasttime(message.guild.id, message.author.id)
        
        xp_gained = message_text.count(' ')
        xp_cooldown = CONFIG_DATA[str(message.guild.id)]['cfg']['xp_cooldown']
        xp_cap = CONFIG_DATA[str(message.guild.id)]['cfg']['max_xp_per_message']
        
        if ((time.time() - lasttime) > xp_cooldown) and (xp_gained > 0):
            if xp_gained > xp_cap:
                xp_gained = xp_cap
                
            new_xp = xp + xp_gained
            if new_xp >= 5 * (old_level ** 2) + 1:
                new_level = old_level + 1
            else:
                new_level = old_level
            
            if new_level in CONFIG_DATA[str(message.guild.id)]['cfg']['levels_to_ping_user']:
                bot_channel = get(message.guild.text_channels,
                                  name=CONFIG_DATA[str(message.guild.id)]['cfg']['bot_messages_channel_name'])
                if new_level != old_level:
                    try:
                        await bot_channel.send(f'{message.author.mention} Has Reached Level {new_level}!')
                    except AttributeError:
                        bot_channel_name = CONFIG_DATA[str(message.guild.id)]['cfg']['bot_messages_channel_name']
                        await message.guild.create_text_channel(channel_name)
                        bot_channel = get(message.guild.text_channels,
                                          name=CONFIG_DATA[str(message.guild.id)]['cfg']['bot_messages_channel_name'])
                        await bot_channel.send(f'{message.author.mention} Has Reached Level {new_level}!')
            
            with conn:
                cursor.execute("DELETE FROM experiencelevels WHERE guildid=:guildid AND userid=:userid",
                               {'guildid': message.guild.id, 'userid': message.author.id})
            with conn:
                cursor.execute("INSERT INTO experiencelevels VALUES (:guildid, :userid, :newlevel, :newexp, :newlasttime)",
                               {'guildid': message.guild.id, 'userid': message.author.id,
                                'newlevel': new_level, 'newexp': new_xp, 'newlasttime': int(time.time())})
            
            for index, role_level in enumerate(CONFIG_DATA[str(message.guild.id)]['cfg']['levels_with_roles']):
                if new_level >= role_level:
                    role_name = CONFIG_DATA[str(message.guild.id)]['cfg']['level_role_names'][index]
                    role = get(message.guild.roles, name=role_name)
                    if role is None:
                        await message.guild.create_role(name=role_name)
                        role = get(message.guild.roles, name=role_name)
                    await message.author.add_roles(role)

        await client.process_commands(message)


# Things to do when a command throws an error
@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f'This command is currently on cooldown. Please try again in {error.retry_after} seconds.')
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send('I\'m sorry, I don\'t know that command. Try $help for a list of commands.')
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send('I\'m sorry, you seem to be missing permissions for this command.')
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send('I\'m sorry, you seem to be missing an argument for this command.')
    else:
        raise error
    

@client.command()
@commands.has_permissions(administrator=True)
async def changecooldown(ctx, new_cooldown):
    """Admin Only: Changes Experience Cooldown"""
    
    global CONFIG_DATA
    
    try:
        CONFIG_DATA[str(ctx.guild.id)]['cfg']['xp_cooldown'] = int(new_cooldown)
        with open('configurations.json', 'w') as f:
            json.dump(CONFIG_DATA, f, indent=2)
            
        await ctx.send(f'Experience Cooldown Changed to {new_cooldown} seconds')
    except ValueError:
        await ctx.send('Error: Please Enter a Valid Integer')


@client.command()
@commands.has_permissions(administrator=True)
async def changemaxxp(ctx, new_max_xp):
    """Admin Only: Changes Maximum Experience Per Message"""
    
    global CONFIG_DATA
    
    try:
        CONFIG_DATA[str(ctx.guild.id)]['cfg']['max_xp_per_message'] = int(new_max_xp)
        with open('configurations.json', 'w') as f:
            json.dump(CONFIG_DATA, f, indent=2)
            
        await ctx.send(f'Maximum Message Experience Changed to {new_max_xp} exp')
    except ValueError:
        await ctx.send('Error: Please Enter a Valid Integer')


@client.command()
@commands.has_permissions(administrator=True)
async def listautoresponses(ctx):
    """Admin Only: Lists All Auto-Responses"""
    
    global CONFIG_DATA
    
    await ctx.send(json.dumps(CONFIG_DATA[str(ctx.guild.id)]['cfg']['auto_responses'], indent=2))


@client.command()
@commands.has_permissions(administrator=True)
async def addautoresponse(ctx, new_trigger, new_response):
    """Admin Only: Add New Auto-Response"""
    
    global CONFIG_DATA
    
    if new_trigger in CONFIG_DATA[str(ctx.guild.id)]['cfg']['auto_responses']:
        CONFIG_DATA[str(ctx.guild.id)]['cfg']['auto_responses'][new_trigger.lower()].append(new_response)
    else:
        CONFIG_DATA[str(ctx.guild.id)]['cfg']['auto_responses'][new_trigger.lower()] = [new_response]
    
    with open('configurations.json', 'w') as f:
        json.dump(CONFIG_DATA, f, indent=2)
    
    await ctx.send(f'Added Response "{new_response}" for phrase "{new_trigger}"')
        
        
@client.command()
@commands.has_permissions(administrator=True)
async def delautoresponse(ctx, del_trigger, del_response):
    """Admin Only: Delete Auto-Response"""
    
    global CONFIG_DATA
    
    if del_trigger in CONFIG_DATA[str(ctx.guild.id)]['cfg']['auto_responses']:
        if del_response in CONFIG_DATA[str(ctx.guild.id)]['cfg']['auto_responses'][del_trigger]:
            if len(CONFIG_DATA[str(ctx.guild.id)]['cfg']['auto_responses'][del_trigger]) > 1:
                CONFIG_DATA[str(ctx.guild.id)]['cfg']['auto_responses'][del_trigger].remove(del_response)
            else:
                del CONFIG_DATA[str(ctx.guild.id)]['cfg']['auto_responses'][del_trigger]
            
            with open('configurations.json', 'w') as f:
                json.dump(CONFIG_DATA, f, indent=2)
                
            await ctx.send(f'Removed Response "{del_response}" for phrase "{del_trigger}"')
        else:
            await ctx.send('Error: Please Enter a Current Response for the Entered Trigger (Case Sensitive)')
    else:
        await ctx.send('Error: Please Enter a Current Trigger Phrase (Case Sensitive)')


@client.command()
@commands.has_permissions(administrator=True)
async def setautodm(ctx, new_message):
    """Admin Only: Configures Automatic DM"""
    
    global CONFIG_DATA
    
    CONFIG_DATA[str(ctx.guild.id)]['cfg']['auto_dm_message'] = new_message
    
    with open('configurations.json', 'w') as f:
        json.dump(CONFIG_DATA, f, indent=2)
        
    await ctx.send(f'Set Automatic DM to "{new_message}"')


@client.command()
@commands.has_permissions(administrator=True)
async def autodm(ctx):
    """Admin Only: Automatically DM's Mentioned Users"""
    
    global CONFIG_DATA
    
    dm_message = CONFIG_DATA[str(ctx.guild.id)]['cfg']['auto_dm_message']
    
    if dm_message:
        for mention in ctx.message.mentions:
            await mention.send(dm_message)
        await ctx.send('Done!')
    else:
        await ctx.send('I\'m sorry, your automatic DM has not been configured.')
    await ctx.message.delete()


# Debug cog
class Debug(commands.Cog):
    """Developer/Latency Commands"""
    
    def __init__(self, client):
        self.client = client

    @commands.command()
    async def ping(self, ctx):
        """Latency Command"""
        
        await ctx.send(f'{ctx.author.mention} Pong! {round(self.client.latency * 1000)}ms')


# Experience cog
class Exp(commands.Cog):
    """Experience Related Commands"""
    
    def __init__(self, client):
        self.client = client
        
    @commands.command(aliases=['xp', 'exp'])
    async def experience(self, ctx):
        """Check Your Current Experience"""
        
        xp = get_xp(ctx.guild.id, ctx.author.id)
        await ctx.send(f'{ctx.author.mention}\'s current experience is {xp}')
        
    @commands.command()
    async def level(self, ctx):
        """Check Your Current Level"""
        
        current_level = get_level(ctx.guild.id, ctx.author.id)
        await ctx.send(f'{ctx.author.mention}\'s current level is {current_level}')
        
    @commands.command()
    async def progress(self, ctx):
        """Check Your Progress Towards Your Next Level"""
        
        xp = get_xp(ctx.guild.id, ctx.author.id)
        current_level = get_level(ctx.guild.id, ctx.author.id)
        xp_to_next_level = ((5 * (current_level ** 2)) + 1) - xp
        await ctx.send(f'{ctx.author.mention} needs {xp_to_next_level} more xp to reach level {current_level + 1}')
        
    @commands.command()
    @commands.cooldown(1, 30, commands.BucketType.guild)
    async def leaderboard(self, ctx):
        """Check The Top Experience Earners"""
        
        cursor.execute("SELECT * FROM experiencelevels WHERE guildid=:guildid ORDER BY exp DESC",
                       {'guildid': ctx.guild.id})
        sorted_data = cursor.fetchall()
        list_of_strings = ['Top Users by XP:\n']
        if len(sorted_data) < 10:
            for i, entry in enumerate(sorted_data):
                _, user_id, current_level, xp, _ = entry
                username = self.client.get_user(int(user_id)).name
                list_of_strings.append(f'{i+1}: {username} has {xp}xp and is level {current_level}\n')
        else:
            for i in range(10):
                entry = sorted_data[i]
                _, user_id, current_level, xp, _ = entry
                username = self.client.get_user(int(user_id))
                list_of_strings.append(f'{i+1}: {username} has {xp}xp and is level {current_level}\n')
        string_to_send = ''.join(list_of_strings)
        await ctx.send(string_to_send)
            

# Memes cog (only active when config.do_reddit=True)
class Memes(commands.Cog):
    """Meme Commands"""
    
    def __init__(self, client, reddit):
        self.client = client
        self.reddit = reddit
        
    @commands.command()
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def doit(self, ctx):
        """Summon A Prequel Meme from r/PrequelMemes"""
        
        subreddit = await self.reddit.subreddit('prequelmemes')
        posts = subreddit.hot(limit=50)
        post_info = []
        async for post in posts:
            url = post.url
            title = post.title
            author = post.author
            if url.endswith(('.jpg', '.png', '.gif', '.jpeg')):
                post_info.append((title, url, author))
        random_choice = choice(post_info)
        post_title, image_url, post_author = random_choice
        await ctx.send(f'{post_title} (Credit to u/{post_author})')
        await ctx.send(image_url)


# Enable cogs
client.add_cog(Debug(client))
client.add_cog(Exp(client))
client.add_cog(Memes(client, reddit))

# Run bot
client.run(config.discord_secret)
