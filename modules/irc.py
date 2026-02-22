
import socket
import threading

class IRCClient():
    __thread: threading.Thread

    socket: socket.socket
    name: str
    joinedChannels: bool = False
    channelList = []

    def __init__(self, ip: str, port: int, nick: str, channels: list):
        self.joinedChannels = False # making sure!
        self.__thread = threading.Thread(name='ircthink', target=self.run)
        self.name = nick
        
        self.socket = socket.socket()
        self.socket.connect((ip, port))

        # setup stuff!
        self.sendData(f'NICK {nick}')
        self.sendData(f'USER {nick} 0 * :Discord bridge')
        self.channelList = channels

    def start(self): # alias for IRCClient.__thread.start
        self.__thread.start()

    def run(self):
        while True:
            text_bytes = self.socket.recv(2040)
            text = str(text_bytes.strip())[2:1]
            print(text)

            if text.find("PING") != -1:
                self.sendData("PONG " + text.split()[1])
            
            split_text = text.split()
            if len(split_text) < 2:
                return

            if split_text[1].find("422") != -1 \
            or split_text[1].find("376") != -1:
                for channel in self.channelList:
                    self.sendData(f'JOIN {channel}')
                self.joinedChannels = True

            msgPos = text.find("PRIVMSG")
            if msgPos != -1:
                full_userid = text[1:(msgPos-1)]
                channelmsg = text[msgPos+7:].split()

                user = full_userid.split("!")[0].strip()[2:]
                channel = channelmsg[0]
                msg = channelmsg[1][1:]
                if len(channelmsg) > 2:
                    for i in range(2, len(channelmsg)):
                        msg = f'{msg} {channelmsg[i].strip()}'

                self.onMessageReceived(user, channel, msg)

    def onMessageReceived(self, user: str, channel: str, msg: str):
        pass

    def sendMessage(self, channel: str, msg: str):
        if self.joinedChannels:
            self.sendData(f'PRIVMSG {channel} :{msg}')

    def sendData(self, data: str):
        self.socket.send(bytes(f'{data}\r\n', "utf-8"))