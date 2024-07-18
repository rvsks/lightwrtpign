from telethon.sync import TelegramClient
from telethon.sessions import StringSession
import os
from dotenv import load_dotenv

load_dotenv()

api_id = int(os.getenv('API_ID'))
api_hash = os.getenv('API_HASH')

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("Ваша новая строка сессии:", client.session.save())
