import os

import paramiko

import config


def _ssh():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=config.SFTP_HOST,
        port=config.SFTP_PORT,
        username=config.SFTP_USER,
        password=config.SFTP_PASS,
        timeout=30,
    )
    return client.open_sftp()


def sync_all():
    os.makedirs(config.CACHE_DIR, exist_ok=True)
    sftp = _ssh()
    try:
        remote_files = [
            (config.SERVER_SIGNIN_DB, os.path.join(config.CACHE_DIR, "Database.db")),
            (config.SERVER_ACCOUNTS_AOF, os.path.join(config.CACHE_DIR, "accounts.aof")),
            (config.SERVER_USERCACHE, os.path.join(config.CACHE_DIR, "usercache.json")),
        ]
        for remote, local in remote_files:
            try:
                sftp.get(remote, local)
            except FileNotFoundError:
                pass
    finally:
        sftp.close()
    return True
