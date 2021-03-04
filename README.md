# BeaverBot
A Discord bot for Dam Discord Directory

# Configuration
To edit the default configuration that will be added to each new server your bot joins, change default.json. Individual configurations will
be stored in configurations.json, and the name of the server is listed for convenience in addition to the ID used as a key.

Leave everything you find in a list, in a list. Even if you are only using one item

**Make sure to rename sample_config.py to config.py and go through it before launching**

# Configuration of FAQ and Auto-Responses
Automatic Responses and FAQ are configured using dictionaries in config.py. The key is the substring to check for in the case of Auto-Responses,
or the uncompiled regex rawstring in the case of FAQ. The corresponding value is the response, which can be either a docstring or a standard
string. For both regex rawstrings and substrings to check for, please use lowercase letters. Beaver Bot uses the .lower() method on the message
text before comparing.
