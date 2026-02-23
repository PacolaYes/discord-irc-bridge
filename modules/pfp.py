
import validators
import pathlib
import json

class IRCpfp:
    filepath: pathlib.Path
    pfps: dict = {}
    
    def __init__(self, path: str):
        self.filepath = pathlib.Path(path)

        if self.filepath.exists():
            data = ""
            with open(self.filepath, "r") as file:
                data = file.read()

            self.pfps = json.loads(data)
        else:
            self.filepath.touch()
            self.save()
    
    def save(self):
        with open(self.filepath, "w") as file:
            file.write(json.dumps(self.pfps, indent=4))
            
    def changePFP(self, user: str, pfp: str):
        if not validators.url(pfp): # discord will prob deny it if the image isn't valid anyways :þ
            return False
        
        self.pfps[user] = pfp
        self.save()
        return True