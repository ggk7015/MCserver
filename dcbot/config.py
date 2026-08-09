import os

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")
GUILD_IDS = [int(x) for x in os.environ.get("GUILD_IDS", "").split(",") if x.strip()]

SFTP_HOST = os.environ.get("SFTP_HOST", "")
SFTP_PORT = int(os.environ.get("SFTP_PORT", "22"))
SFTP_USER = os.environ.get("SFTP_USER", "")
SFTP_PASS = os.environ.get("SFTP_PASS", "")

SERVER_SIGNIN_DB = os.environ.get("SERVER_SIGNIN_DB", "/plugins/LiteSignIn/Database.db")
SERVER_ACCOUNTS_AOF = os.environ.get("SERVER_ACCOUNTS_AOF", "/plugins/DiscordSRV/accounts.aof")
SERVER_USERCACHE = os.environ.get("SERVER_USERCACHE", "/usercache.json")

CACHE_DIR = os.environ.get("CACHE_DIR", os.path.join(BASE_DIR, "data", "cache"))
LOCAL_DB = os.environ.get("LOCAL_DB", os.path.join(BASE_DIR, "data", "dcbot.db"))

SYNC_INTERVAL = int(os.environ.get("SYNC_INTERVAL", "900"))
