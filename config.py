# config.py
import json
import os

CONFIG_FILE = "servers.json"

def load_servers():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            return {"8.8.8.8": "Google DNS", "1.1.1.1": "Cloudflare DNS"}
    return {"8.8.8.8": "Google DNS", "1.1.1.1": "Cloudflare DNS"}

def save_servers(servers: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(servers, f, indent=4)
