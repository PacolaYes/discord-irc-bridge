
from modules.irc import IRCClient # handles base irc functionality
from modules.settings import getSettings
from modules.pfp import IRCpfp # handles gettings pfps when going IRC -> discord

import discord
from discord.ext import tasks

import sys
import re

pfp = IRCpfp("pfps.json") # super secure handling of this :))))))
settings: dict = getSettings("settings.json")
channels: dict = settings.get("discord-irc_channels")

if channels is None:
    sys.exit("'discord-irc_channels' not found in settings.json.")

class DiscordClient(discord.Client): # handle discord -> irc here, as discord.py already handles base functionality
    irc: IRCClient
    irc_msgs: dict = {}
    irc_next_msgs: dict = {}

    async def on_message(self, message: discord.Message):
        channel = message.channel.id

        if message.webhook_id:
            for webhook in await message.channel.webhooks():
                if webhook.id == message.webhook_id \
                and webhook.name == "IRC Bridge":
                    return

        irc_channel = channels.get(str(channel))
        if irc_channel:
            lines = message.content.splitlines()

            self.irc.sendMessage(irc_channel, f'<{message.author.display_name}> {lines[0]}')
            i = 0
            for line in lines:
                if i != 0:
                    self.irc.sendMessage(irc_channel, line)

                i += 1

    async def setup_hook(self):
        self.sendStoredMessages.start()

    @tasks.loop(seconds=0.1)
    async def sendStoredMessages(self):
        if len(self.irc_msgs) <= 0:
            self.irc_msgs = self.irc_next_msgs
            self.irc_next_msgs = {}

        if len(self.irc_msgs) > 0:
            for channelid, user_n_msgs in self.irc_msgs.items():
                channel = self.get_channel(int(channelid))

                foundWebhook: discord.Webhook = None
                for webhook in await channel.webhooks():
                    if webhook.name == "IRC Bridge":
                        foundWebhook = webhook
                        break

                if foundWebhook is None:
                    foundWebhook = await channel.create_webhook(name="IRC Bridge")

                for user, messages in user_n_msgs.items():
                    for message in messages:
                        await foundWebhook.send(content=message, username=user, avatar_url=pfp.pfps.get(user))

            self.irc_msgs = {}

def insert_str(string, str_to_insert, index):
    return string[:index] + str_to_insert + string[index:]

class IRCBridge(IRCClient):
    discord: discord.Client

    def __replaceFormatting(self, msg: str, formatting: str, replacement: str):
        isFormatting = False
        formats = 0

        new_msg = msg
        for i in range(0, len(msg)):
            char = msg[i:i+1]
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

    def formattingParse(self, message: str):
        new_msg = message

        # escape characters that we handle formatting for already
        new_msg = new_msg.replace("*", "\\*") # should handle both bold and italics
        new_msg = new_msg.replace("_", "\\_") # should handle both italics and underline
        new_msg = new_msg.replace("~", "\\~")

        # ONLY changes IRC formatting into Discord's one, it WILL NOT handle if its one right beside the other
        new_msg = self.__replaceFormatting(new_msg, "\02", "**") # handle bold
        new_msg = self.__replaceFormatting(new_msg, "\x1d", "*") # handle italics
        new_msg = self.__replaceFormatting(new_msg, "\x1f", "__") # handle underline
        new_msg = self.__replaceFormatting(new_msg, "\x1e", "~~") # handle strikethrough

        # just delete the color stuff, not handling all of that :P
        new_msg = re.sub(r"\x03(?P<fg>\d{2})(,(?P<bg>\d{2}))?", "", new_msg) # copied from https://github.com/impredicative/ircstyle/blob/ec4f96e9910f0b896c9b0e84af39700c48f0c192/ircstyle/__init__.py#L135 as im very smart

        split_msg = new_msg.split() # handle /me!
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

                if irc_channel == channel:
                    if self.discord.irc_next_msgs.get(discord_channel):
                        users = self.discord.irc_next_msgs[discord_channel]

                        if users.get(user):
                            users[user].append(message)
                        else:
                            users[user] = [message]
                    else:
                        self.discord.irc_next_msgs[discord_channel] = {
                            user: [message]
                        }

# init discord stuff
intents = discord.Intents.default()
intents.message_content = True
discord = DiscordClient(intents=intents)

# init irc stuff
irc_channels = list(channels.values())
irc = IRCBridge(settings["irc_host"], settings["irc_port"], settings["irc_name"], irc_channels)

discord.irc = irc
irc.discord = discord

irc.start()
discord.run(settings["discord_token"])