
from modules.irc import IRCClient

class IRCBridge(IRCClient):
    def onMessageReceived(self, user: str, channel: str, message: str):
        print(f'{user} sent "{message}" on {channel}')
        if channel == self.name:
            self.sendMessage(user, f'You\'ve said: "{message}"')

irc = IRCBridge("freak.farted.net", 6669, "testBot", ["#general"])

irc.start()
