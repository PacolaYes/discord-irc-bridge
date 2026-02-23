
from modules.irc import IRCClient # handles base irc functionality
from modules.settings import getSettings
import sys
import discord
from discord.ext import tasks

settings: dict = getSettings("settings.json")
channels: dict = settings.get("discord-irc_channels")

if channels is None:
    sys.exit("'discord-irc_channels' not found in settings.json.")

class DiscordClient(discord.Client): # handle discord -> irc here, as discord.py already handles base functionality
    irc: IRCClient
    irc_msgs: dict = {}

    async def on_message(self, message: discord.Message):
        channel = message.channel.id

        if discord.message.webhook_id:
            for webhook in await discord.message.channel.webhooks():
                if webhook.id == discord.message.webhook_id \
                and webhook.name == "IRC Bridge":
                    return

        irc_channel = channels[str(channel)]
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
    
    @tasks.loop(seconds=0.5)
    async def sendStoredMessages(self):
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
                        await foundWebhook.send(content=message, username=user, avatar_url=None)
            
            self.irc_msgs = {}

class IRCBridge(IRCClient):
    discord: discord.Client

    def onMessageReceived(self, user: str, channel: str, message: str):
        print(user, channel, message)
        for discord_channel, irc_channel in channels.items():
            if irc_channel == channel:
                if self.discord.irc_msgs.get(discord_channel):
                    users = self.discord.irc_msgs[discord_channel]

                    if users[user]:
                        users[user].append(message)
                    else:
                        users[user] = [message]
                else:
                    self.discord.irc_msgs[discord_channel] = {
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