from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = '23330392'
api_hash = '924f6a253b0eb0a13a987ce36b4ddf5d'

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print(client.session.save())
