# BeaverBot
A Discord bot for Dam Discord Directory

# Configuration
**Make sure to rename sample_config.py to config.py once you are done configuring. The bot will not function otherwise**

Go through the config.py file replacing everything that has a nonexistent variable or invalid value with a valid value.
If you change do_reddit to False, you do not need to enter a reddit Client ID, Secret ID or User Agent, you can enter a blank string instead.
Changing do_reddit to false will also disable the subreddit uplink feature.

If something is in a list, leave your value in a list, even if you are only using one value. It is programmed for multiple possible values but will work with one.

# Configuration of FAQ and Auto-Responses
Automatic Responses and FAQ are configured using dictionaries in config.py. The key is the substring to check for in the case of Auto-Responses,
or the uncompiled regex rawstring in the case of FAQ. The corresponding value is the response, which can be either a docstring or a standard string.
For both regex rawstrings and substrings to check for, please use lowercase letters. Beaver Bot uses the .lower() method on the message text before comparing.
