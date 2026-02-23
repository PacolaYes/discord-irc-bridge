
import json
import sys
from pathlib import Path

def getSettings(path: str):
    truePath = Path(path)

    if truePath.exists():
        data = ""
        with open(truePath, "r") as file:
            data = file.read()

        return json.loads(data)
    else:
        base_json = {
            "discord_token": "1234567890",
            "discord-irc_channels": {
                "1234567890": "#temp"
            },
            "irc_host": "localhost",
            "irc_port": 6667,
            "irc_name": "discordBridge"
        }
        with open(truePath, "x") as file:
            file.write(json.dumps(base_json, indent=4))
        
        sys.exit("Define your settings.")