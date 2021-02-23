import discord

command_prefix = '$'

discord_secret = YOUR_DISCORD_SECRET_KEY_HERE

do_reddit = True
do_reddit_uplink = True

reddit_client = YOUR_REDDIT_CLIENT_ID_HERE
reddit_secret = YOUR_REDDIT_SECRET_ID_HERE
reddit_user_agent = 'Sample User Agent'

status = discord.ActivityType.watching
status_message = 'for Error Reports'

auto_responses = {'sample prompt':['sample response 1',
                                   'sample response 2']
                  }

faq_guild_ids = [YOUR_GUILD_ID_HERE]
faq = {r'REGEX_STRING_HERE':'''FAQ RESPONSE HERE'''
       }

uplink_guild_ids = [YOUR_GUILD_ID_HERE]
uplink_channel_name = 'info-updates'
uplink_subreddits = ['SUBREDDIT1', 'SUBREDDIT2']

xp_cooldown = 10
max_xp_per_message = 25

levels_with_roles = [5, 10, 20]
bot_messages_channel_name = 'bot-messages'

levels_to_ping_user = [5, 10, 20]
levels_to_ping_everyone = [50, 100]
