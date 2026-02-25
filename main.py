
from modules.irc import IRCClient # handles base irc functionality
from modules.settings import getSettings
from modules.pfp import IRCpfp # handles gettings pfps when going IRC -> discord

import discord
from discord.ext import tasks
import dismoji
import validators

import sys
import atexit
import re

pfp = IRCpfp("pfps.json") # super secure handling of this :))))))
settings: dict = getSettings("settings.json")
channels: dict = settings.get("discord-irc_channels")

if channels is None:
    sys.exit("'discord-irc_channels' not found in settings.json.")

# Source - https://stackoverflow.com/a/76073981
# Posted by Hazzu, modified by community. See post 'Timeline' for change history
# Retrieved 2026-02-24, License - CC BY-SA 4.0
EMOJI_REGEX = r'<(?P<animated>a?):(?P<name>[a-zA-Z0-9_]{2,32}):(?P<id>[0-9]{18,22})>'

class DiscordClient(discord.Client): # handle discord -> irc here, as discord.py already handles base functionality
    irc: IRCClient
    irc_msgs: dict = {}
    irc_next_msgs: dict = {}

    stored_webhooks: dict = {}
    stored_messages: dict = {} # used for irc replies

    def __subEmojis(self, match: re.Match):
        extension = "gif" if match["animated"] else "png"
        return f'{match["name"]}(https://cdn.discordapp.com/emojis/{match["id"]}.{extension})'
    
    # converts the IDs for channels, emojis
    def convertIDs(self, message: discord.Message):
        new_msg = message.content
        
        # handle channel ids
        # send "\I*channel not available*\I" where \I toggles italic
        for match in re.finditer(r'<#[0-9]+>', new_msg):
            channelstr = match.group(0)
            channelid = channelstr[2:-1]

            replace_str = channels.get(channelid)
            if not replace_str:
                replace_str = "\x1d*channel not available*\x1d"

            new_msg = new_msg.replace(channelstr, replace_str, 1)
        
        # handle custom emojis!
        new_msg = re.sub(EMOJI_REGEX, self.__subEmojis, new_msg)

        # handle mentions
        was_mentioned = {}
        for user in message.mentions:
            if not was_mentioned.get(user.id):
                new_msg = new_msg.replace(f'<@{user.id}>', f'@{user.display_name}')
                was_mentioned[user.id] = True

        # handle stickers :þ
        for sticker in message.stickers:
            if new_msg == "" or new_msg == " ":
                new_msg = sticker.url
            else:
                new_msg = f'{new_msg} {sticker.url}'

        # handle attachments
        for attachment in message.attachments:
            new_msg = f'{new_msg} {attachment.url}'

        return new_msg
    
    # prob not necessary, but i'm keeping function
    # even after i learnt re.sub can do this
    # (i should read the documentation properly more)
    def __replaceFormatting(self, message: str, regex: str, replace: str):
        regex = re.escape(regex)
        return re.sub(rf'(?P<prefix>{regex})(?P<message>[\s\S]+?)(?P<suffix>{regex})', lambda match: f'{replace}{match.group("message")}{replace}', message)

    def formattingParse(self, message: discord.Message):
        msg = self.convertIDs(message)
        split_msg = msg.split(" ")
        new_msg = ""

        for cur_msg in split_msg:
            if not validators.url(cur_msg):
                cur_msg = self.__replaceFormatting(cur_msg, '**', '\x02') # handle bold
                cur_msg = self.__replaceFormatting(cur_msg, '*', '\x1d') # handle italics
                cur_msg = self.__replaceFormatting(cur_msg, '__', '\x1f') # handle underline
                cur_msg = self.__replaceFormatting(cur_msg, '_', '\x1d') # handle italics²
                cur_msg = self.__replaceFormatting(cur_msg, '~~', '\x1e') # handle strikethrough
            
            new_msg = f'{new_msg} {cur_msg}'

        return new_msg

    async def on_message(self, message: discord.Message):
        channel = message.channel.id

        if message.webhook_id:
            for webhook in await message.channel.webhooks():
                if webhook.id == message.webhook_id \
                and webhook.name == "IRC Bridge":
                    return

        irc_channel = channels.get(str(channel))
        if irc_channel:
            msgs = []

            if message.reference and message.type == discord.MessageType.reply:
                reply: discord.Message = [msg for msg in self.cached_messages if msg.id == message.reference.message_id]
                if not reply:
                    channel: discord.Channel = self.get_channel(message.reference.channel_id)
                    reply = await channel.fetch_message(message.reference.message_id)
                else:
                    reply = reply[0]
                
                try:
                    # why does author just not have the guild thing ????????
                    author = await reply.channel.guild.fetch_member(reply.author.id)
                except discord.errors.NotFound:
                    author = reply.author
                
                msgs.append(f'↩ <{author.display_name}> {self.formattingParse(reply)}')
            
            msgs.append(self.formattingParse(message))

            self.stored_messages[message.author.display_name] = msgs[-1]

            for i, msg in enumerate(msgs):
                lines = msg.split("\n")

                prefix = f'<{message.author.display_name}> ' if i == len(msgs)-1 else ''
                self.irc.sendMessage(irc_channel, f'{prefix}{lines[0]}')
                for i in range(1, len(lines)):
                    self.irc.sendMessage(irc_channel, f'^^^ {lines[i]}')

    async def setup_hook(self):
        self.sendStoredMessages.start()

    @tasks.loop(seconds=0.2)
    async def sendStoredMessages(self):
        if len(self.irc_msgs) <= 0:
            self.irc_msgs = self.irc_next_msgs
            self.irc_next_msgs = {}

        if len(self.irc_msgs) > 0:
            for channelid, msgs in self.irc_msgs.items():
                channel = self.get_channel(int(channelid))

                if channel is None:
                    print("Something is wrong :(")
                    return

                foundWebhook: discord.Webhook = self.stored_webhooks.get(channelid)
                if foundWebhook is None:
                    for webhook in await channel.webhooks():
                        if webhook.name == "IRC Bridge":
                            foundWebhook = webhook
                            break

                    if foundWebhook is None:
                        foundWebhook = await channel.create_webhook(name="IRC Bridge")

                if foundWebhook is None:
                    return

                for dictionary in msgs:
                    user = dictionary.get("user")
                    reply_user = dictionary.get("reply")
                    message = dictionary.get("message")
                    if reply_user and self.stored_messages.get(reply_user):
                        message = f'-# ↩ {reply_user}: "{self.stored_messages[reply_user][1:100]}"\n{message}'

                    self.stored_messages[user] = await foundWebhook.send(content=message, username=user, avatar_url=pfp.pfps.get(user))

            self.irc_msgs = {}

class IRCBridge(IRCClient):
    discord: DiscordClient

    def __replaceFormatting(self, msg: str, formatting: str, replacement: str):
        isFormatting = False
        formats = 0

        new_msg = msg
        # NOTE: this can maybe be done with a re.sub function thingie???
        # can prob check later :P
        for i, char in enumerate(msg):
            if char == formatting:
                isFormatting = not isFormatting
                formats += 1
                new_msg = new_msg[:i] + "\x81" + new_msg[i+1:]
            elif char == "\x0f" \
            and isFormatting:
                isFormatting = False
                formats += 1
                new_msg = new_msg[:i] + "\x81" + new_msg[i:]

        if formats % 2 == 1:
            new_msg = new_msg + replacement

        return new_msg.replace("\x81", replacement)

    def __replaceEmoji(self, match: re.Match):
        string = match["emoji_name"]
        for emoji in self.discord.emojis:
            if emoji.name in string:
                prefix = "a:" if emoji.animated else ""
                return f'<{prefix}{emoji.name}:{emoji.id}>'
    
    def __replaceChannel(self, match):
        for discord_id, irc_id in channels.items():
            if match[1] == irc_id[1:]:
                return f'<#{discord_id}>'
        return "<#0>"

    def convertChannel(self, msg: str):
        return re.sub(r'#(\S+)', self.__replaceChannel, msg)

    def formattingParse(self, message: str):
        split_msg = message.split(" ")
        new_msg = ""

        # TODO: prob find a better way for this
        for msg in split_msg:
            if not validators.url(msg):
                msg = dismoji.emojize(msg)
                msg = self.convertChannel(msg)

                # escape characters that we handle formatting for already
                msg = msg.replace("*", "\\*") # should handle both bold and italics
                msg = msg.replace("_", "\\_") # should handle both italics and underline
                msg = msg.replace("~", "\\~")

                # ONLY changes IRC formatting into Discord's one, it WILL NOT handle if its one right beside the other
                msg = self.__replaceFormatting(msg, "\02", "**") # handle bold
                msg = self.__replaceFormatting(msg, "\x1d", "*") # handle italics
                msg = self.__replaceFormatting(msg, "\x1f", "__") # handle underline
                msg = self.__replaceFormatting(msg, "\x1e", "~~") # handle strikethrough

            # just delete the color stuff, not handling all of that :P
            msg = re.sub(r"\x03(?P<fg>\d{2})(,(?P<bg>\d{2}))?", "", msg) # copied from https://github.com/impredicative/ircstyle/blob/ec4f96e9910f0b896c9b0e84af39700c48f0c192/ircstyle/__init__.py#L135 as im very smart
            msg = re.sub(r'(:)(?P<emoji_name>\S+?)(:)', self.__replaceEmoji, msg)
            new_msg = f'{new_msg} {msg}'

        split_msg = new_msg.split() # handle /me!
        if len(split_msg) > 0:
            if split_msg[0].find("ACTION") != -1:
                new_msg = f'^^^ *{split_msg[1]}'
                for i in range(2, len(split_msg)):
                    new_msg = f'{new_msg} {split_msg[i]}'
                new_msg = new_msg + "*"

        return new_msg.strip() # get rid of the rest pls

    def onMessageReceived(self, user: str, channel: str, message: str):
        if channel == self.name:
            if pfp.changePFP(user, message):
                self.sendMessage(user, "Successfully updated your Discord pfp!")
            else:
                self.sendMessage(user, "Please only send a direct link to an image.")
                self.sendMessage(user, "Supported types are: png, jpeg, jpg, gif, webp")
        else:
            for discord_channel, irc_channel in channels.items():
                message = self.formattingParse(message)

                if message == "" or message == " ":
                    message = "** **"

                reply = None
                match = re.match(r'(\s*)(?P<user>\S+) [»>]( )+(?P<message>\S+)', message)
                if match:
                    reply = match["user"]
                    message = message[match.start("message"):]

                if irc_channel == channel:
                    dictionary = {
                        "user": user,
                        "message": message,
                        "reply": reply
                    }
                    
                    if self.discord.irc_next_msgs.get(discord_channel):
                        self.discord.irc_next_msgs[discord_channel].append(dictionary)
                    else:
                        self.discord.irc_next_msgs[discord_channel] = [dictionary]
    
    def onUserLeave(self, user: str, message: str):
        if user == self.name:
            message = "Bridge closed."
        elif not settings.get("broadcast-join-leaves"):
            return

        dictionary = {
            "message": f'{user} has left ({message})'
        }
        
        for discord_channel in channels.keys():
            if self.discord.irc_next_msgs.get(discord_channel):
                self.discord.irc_next_msgs[discord_channel].append(dictionary)
            else:
                self.discord.irc_next_msgs[discord_channel] = [dictionary]
    
    def onUserJoin(self, user: str, channel: str):
        dictionary: dict = {}
        if user == self.name:
            dictionary["message"] = "Bridge opened."
        elif not settings.get("broadcast-join-leaves"):
            return
        else:
            dictionary["message"] = f'{user} has joined ({channel})'
        
        for discord_channel in channels.keys():
            if self.discord.irc_next_msgs.get(discord_channel):
                self.discord.irc_next_msgs[discord_channel].append(dictionary)
            else:
                self.discord.irc_next_msgs[discord_channel] = [dictionary]

# init discord stuff
intents = discord.Intents.default()
intents.message_content = True
discord_bot = DiscordClient(intents=intents)

# init irc stuff
irc_channels = list(channels.values())
irc = IRCBridge(settings["irc_host"], settings["irc_port"], settings["irc_name"], irc_channels)

discord_bot.irc = irc
irc.discord = discord_bot

def onExit():
    irc.quit("Bridge closed.")

atexit.register(onExit)

irc.start()
discord_bot.run(settings["discord_token"])