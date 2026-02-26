
import socket
import threading
import time

class Buffer: # thnak yuo https://stackoverflow.com/a/67826680
    def __init__(self,sock):
        self.sock = sock
        self.buffer = b''

    def get_line(self):
        while b'\r\n' not in self.buffer:
            data = self.sock.recv(1024)
            if not data: # socket closed
                return None
            self.buffer += data
        line,sep,self.buffer = self.buffer.partition(b'\r\n')
        return line.decode()

class IRCClient():
    __thread: threading.Thread
    socket: socket.socket

    name: str
    password: str = None

    identified: bool = False
    prevTime: float = 0
    joinedChannels: bool = False
    channelList = []

    def __init__(self, ip: str, port: int, nick: str, channels: list, password):
        self.joinedChannels = False # making sure!
        self.__thread = threading.Thread(name='ircthink', target=self.run)

        self.name = nick
        self.password = password # super necessary

        self.prevTime = time.perf_counter()
        
        self.socket = socket.socket()
        self.socket.connect((ip, port))

        # setup stuff!
        self.sendData(f'NICK {nick}')
        self.sendData(f'USER {nick} 0 * :Discord bridge')
        self.channelList = channels
    def start(self): # alias for IRCClient.__thread.start
        self.__thread.start()

    def run(self):
        buffer = Buffer(self.socket)
        while True:
            text = buffer.get_line()
            print(text)

            if text.find("PING") != -1:
                self.sendData("PONG " + text.split()[1])

            if self.joinedChannels and self.password and not self.identified:
                self.sendMessage("NickServ", f'IDENTIFY {self.password}')
                self.identified = True
            
            split_text = text.split()
            if len(split_text) >= 2:
                if split_text[1] == "422" \
                or split_text[1] == "376":
                    for channel in self.channelList:
                        self.sendData(f'JOIN {channel}')

                    self.joinedChannels = True

                msgPos = text.find("PRIVMSG")
                if msgPos != -1:
                    full_userid = text[1:(msgPos-1)]
                    channelmsg = text[msgPos+8:].split(" ")

                    user = full_userid.split("!")[0]
                    channel = channelmsg[0]
                    msg = channelmsg[1][1:]
                    if len(channelmsg) > 2:
                        for i in range(2, len(channelmsg)):
                            msg = f'{msg} {channelmsg[i]}'

                    self.onMessageReceived(user, channel, msg)
                
                msgPos = text.find("QUIT")
                joinPos = text.find("JOIN")
                if msgPos != -1 or joinPos != -1:
                    full_userid = text
                    split_msg = []
                    if msgPos != -1:
                        full_userid = text[1:(msgPos-1)]
                        split_msg = text[msgPos+5:].split(" ")
                    elif joinPos != -1:
                        full_userid = text[1:(joinPos-1)]
                        split_msg = text[joinPos+5:].split(" ")

                    user = full_userid.split("!")[0]
                    msg = split_msg[0][1:]
                    if len(msg) > 1:
                        for i in range(1, len(split_msg)):
                            msg = f'{msg} {split_msg[i]}'
                    
                    if msgPos != -1:
                        self.onUserLeave(user, msg)
                    elif joinPos != -1:
                        self.onUserJoin(user, split_msg[0])

    def quit(self, reason: str):
        self.sendData(bytes(f'QUIT {reason}', "utf-8"))

    def onMessageReceived(self, user: str, channel: str, msg: str):
        pass

    def onUserLeave(self, user: str, message: str):
        pass

    def onUserJoin(self, user: str, channel: str):
        pass

    def sendMessage(self, channel: str, msg: str):
        if self.joinedChannels:
            self.sendData(f'PRIVMSG {channel} :{msg}')

    def sendData(self, data: str):
        self.socket.send(bytes(f'{data}\r\n', "utf-8"))