import os
import logging
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv
from openai import AsyncOpenAI
from supabase import create_client, Client

# Loglarni sozlash
logging.basicConfig(level=logging.INFO)

# .env dan kalitlarni yuklash
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not all([BOT_TOKEN, OPENAI_API_KEY, ADMIN_ID, SUPABASE_URL, SUPABASE_KEY]):
    exit("XATO: .env faylida qaysidir kalit yetishmayapti!")

# Obyektlarni yaratish (Boshqa fayllar shularni chaqirib ishlatadi)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
ai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)