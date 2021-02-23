import re
import asyncpraw
import discord
import sqlite3
import asyncio
import time
from discord.utils import get
from discord.ext import commands
from asyncprawcore.exceptions import RequestException, ServerError
from random import choice
import config

# Allow for bot to get members by id in order to assign roles
intents = discord.Intents.default()
intents.members = True

# Initialize bot instance
client = commands.Bot(command_prefix=config.command_prefix, intents=intents)

# Initialize reddit instance
if config.do_reddit:
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
    guilds = [get(client.guilds, id=guild_id) for guild_id in config.uplink_guild_ids]
    channels = [get(guild.text_channels, name=config.uplink_channel_name) for guild in guilds]
    while True:
        try:
            subreddits = await reddit.subreddit('+'.join(config.uplink_subreddits))
            async for submission in subreddits.stream.submissions(skip_existing=True):
                for index, channel in enumerate(channels):
                    try:
                        await channel.send(f'New post from reddit, go check it out! {submission.url}')
                    except AttributeError:
                        await guilds[index].create_text_channel(config.uplink_channel_name)
                        channels[index] = get(guilds[index].text_channels, name=config.uplink_channel_name)
                        await channels[index].send(f'New post from reddit, go check it out! {submission.url}')
        except (asyncio.TimeoutError, RequestException, ServerError):
            continue


# Things to do when the bot comes online
@client.event
async def on_ready():
    await client.change_presence(activity=discord.Activity(type=config.status,
                                                           name=config.status_message))
    print('Bot Active')
    if config.do_reddit and config.do_reddit_uplink:
        client.loop.create_task(subs_uplink())
        print('Subreddit Uplink Established')


# Things to do whenever there is a message
@client.event
async def on_message(message):
    if not message.author.bot:
        message_text = message.content.lower()
        
        if message.guild.id in config.faq_guild_ids:
            for key in config.faq:
                if re.match(key, message_text):
                    faq_response_message = config.faq[key]
                    await message.channel.send(faq_response_message)
        
        triggers = config.auto_responses.keys()
        for trigger in triggers:
            if trigger in message_text:
                message_choice = choice(config.auto_responses[trigger])
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
        
        if ((time.time() - lasttime) > config.xp_cooldown) and (xp_gained > 0):
            if xp_gained > config.max_xp_per_message:
                xp_gained = config.max_xp_per_message
                
            new_xp = xp + xp_gained
            if new_xp >= 5 * (old_level ** 2) + 1:
                new_level = old_level + 1
            else:
                new_level = old_level
            
            if new_level in config.levels_to_ping_user:
                bot_channel = get(message.guild.text_channels, name=config.bot_messages_channel_name)
                if new_level != old_level:
                    try:
                        await bot_channel.send(f'{message.author.mention} Has Reached Level {new_level}!')
                    except AttributeError:
                        await message.guild.create_text_channel(config.bot_messages_channel_name)
                        bot_channel = get(message.guild.text_channels, name=config.bot_messages_channel_name)
                        await bot_channel.send(f'{message.author.mention} Has Reached Level {new_level}!')
            
            if new_level in config.levels_to_ping_everyone:
                bot_channel = get(message.guild.text_channels, name=config.bot_messages_channel_name)
                if new_level != old_level:
                    try:
                        await bot_channel.send(f'@everyone {message.author.mention} Has Reached Level {new_level}!')
                    except AttributeError:
                        await message.guild.create_text_channel(config.bot_messages_channel_name)
                        bot_channel = get(message.guild.text_channels, name=config.bot_messages_channel_name)
                        await bot_channel.send(f'@everyone {message.author.mention} Has Reached Level {new_level}!')
            
            with conn:
                cursor.execute("DELETE FROM experiencelevels WHERE guildid=:guildid AND userid=:userid",
                               {'guildid': message.guild.id, 'userid': message.author.id})
            with conn:
                cursor.execute("INSERT INTO experiencelevels VALUES (:guildid, :userid, :newlevel, :newexp, :newlasttime)",
                               {'guildid': message.guild.id, 'userid': message.author.id,
                                'newlevel': new_level, 'newexp': new_xp, 'newlasttime': int(time.time())})

            if new_level in config.levels_with_roles:
                role = get(message.guild.roles, name=f"Level {new_level}")
                if role is None:
                    await message.guild.create_role(name=f"Level {new_level}")
                    role = get(message.guild.roles, name=f"Level {new_level}")
                await message.author.add_roles(role)

        await client.process_commands(message)


# Things to do when a command throws an error
@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f'This command is currently on cooldown. Please try again in {error.retry_after} seconds.')
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send('I\'m sorry, I don\'t know that command. Try $help for a list of commands.')
    else:
        raise error
    

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
        
        if config.do_reddit:
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
        else:
            await ctx.send('I\'m sorry, reddit integration seems to be disabled. Please contact your bot operator.')


# Enable cogs
client.add_cog(Debug(client))
client.add_cog(Exp(client))
if config.do_reddit:
    client.add_cog(Memes(client, reddit))

# Run bot
client.run(config.discord_secret)
