from aiohttp import web
import os
import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv
from openai import AsyncOpenAI
from supabase import create_client, Client # Supabase chaqirildi

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types.web_app_info import WebAppInfo
import json

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

# Obyektlarni yaratish
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Supabase bazasiga ulanish
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class BookingState(StatesGroup):
    waiting_for_confirmation = State()

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    
    # 1. Foydalanuvchini bazaga qo'shish (oldingi kod o'zgarishsiz qoladi)
    user_data = {
        "telegram_id": message.from_user.id,
        "full_name": message.from_user.full_name,
        "username": message.from_user.username
    }
    try:
        existing_user = supabase.table("users").select("*").eq("telegram_id", message.from_user.id).execute()
        if not existing_user.data:
            supabase.table("users").insert(user_data).execute()
    except Exception as e:
        logging.error(f"Bazaga yozishda xatolik: {e}")

    # 2. WEB APP TUGMASINI YARATISH (Yangi qo'shilgan qism)
    # SHU YERGA VERCEL YOKI LOCALTUNNEL BERGAN LINKNI QO'YING!
    web_app_url = "https://voluble-baklava-a461f1.netlify.app/" 
    
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🖥 Klub xaritasi", web_app=WebAppInfo(url=web_app_url))]
        ],
        resize_keyboard=True
    )

    # 3. Xabarni tugma bilan yuborish
    await message.answer(
        "Assalomu alaykum! Men GameClub bron botiman 🕹\n\n"
        "Ovozli xabar yuboring yoki pastdagi tugma orqali bo'sh joylarni ko'ring:",
        reply_markup=markup
    )

@dp.message(F.voice)
async def handle_voice(message: types.Message, state: FSMContext):
    wait_msg = await message.answer("🎙 Ovozli xabar qabul qilindi. Matnga o'girilmoqda...")

    voice_id = message.voice.file_id
    file = await bot.get_file(voice_id)
    os.makedirs("temp", exist_ok=True)
    downloaded_file = f"temp/{voice_id}.ogg"
    await bot.download_file(file.file_path, downloaded_file)

    try:
        # Whisper
        with open(downloaded_file, "rb") as audio_file:
            transcription = await client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file,
                prompt="Assalomu alaykum. Menga kompyuter kerak. Bugun soat 20:00 dan 22:00 gacha 3 ta joy bron qilmoqchiman. Yonma-yon bo'lsin. Ikkita, uchta, to'rtta, beshta. Ertalab, kechqurun, abedda. Komp, zanet, qilib ber, aka."
            )
        recognized_text = transcription.text

        # GPT-4o
        await wait_msg.edit_text("⏳ Matn tahlil qilinmoqda...")
        gpt_response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system", 
                    "content": (
                        "Siz kompyuter klubi uchun aqlli bron yordamchisisiz. "
                        "DIQQAT: Matn ovozdan olingan. Unda Ozarbayjoncha yoki xato yozilgan so'zlar bo'lishi mumkin. "
                        "Quyidagi qoidalarga QAT'IY amal qiling:\n\n"
                        "1. Boshlanish vaqti: Matndagi vaqtni topib yozing.\n"
                        "2. Tugash vaqti: FAQAT mijoz aniq aytgan bo'lsa yozing. Yo'qsa 'Aytilmagan' deb yozing.\n"
                        "3. Kompyuterlar soni: Matndan raqamlarni qidiring. Aytilmagan bo'lsa '1 ta' deb oling.\n"
                        "4. Zona/Izoh: Mijozning qo'shimcha talablari bo'lsa yozing, yo'qsa 'Ixtiyoriy'.\n\n"
                        "Javobni qat'iy quyidagi formatda qaytaring:\n"
                        "Boshlanish vaqti: [vaqt]\n"
                        "Tugash vaqti: [vaqt yoki standart]\n"
                        "Kompyuterlar soni: [soni]\n"
                        "Izoh: [VIP/yonma-yon yoki Ixtiyoriy]"
                    )
                },
                {"role": "user", "content": recognized_text}
            ],
            temperature=0.1
        )
        parsed_data = gpt_response.choices[0].message.content

        # State ga saqlash
        await state.update_data(booking_info=parsed_data)
        await state.set_state(BookingState.waiting_for_confirmation)

        final_message = (
            f"🤖 AI agent tushungan ma'lumot:\n\n<b>{parsed_data}</b>\n\n"
            f"✅ Hammasi to'g'rimi? (Tasdiqlash uchun <b>ha</b> deb yozing)"
        )
        await wait_msg.edit_text(final_message, parse_mode="HTML")

    except Exception as e:
        await wait_msg.edit_text(f"❌ Xatolik: {e}")
        
    finally:
        if os.path.exists(downloaded_file):
            os.remove(downloaded_file)
            
            # --- WEB APP DAN KELGAN MA'LUMOTNI USHLAB OLISH ---
@dp.message(F.web_app_data)
async def web_app_handler(message: types.Message):
    # React'dan kelgan JSON ma'lumotni o'qiymiz
    data = message.web_app_data.data
    parsed_data = json.loads(data)
    
    action = parsed_data.get("action")
    pc_id = parsed_data.get("pc_id")
    pc_number = parsed_data.get("pc_number")
    
    if action == "book":
        try:
            # 1. Supabase bazasida kompyuterni "band" (is_active = False) qilib qo'yamiz
            supabase.table("computers").update({"is_active": False}).eq("id", pc_id).execute()
            
            # 2. Mijozga muvaffaqiyatli bron qilingani haqida xabar beramiz
            await message.answer(
                f"🎉 <b>Ajoyib!</b> Siz xarita orqali <b>{pc_number}</b> ni muvaffaqiyatli bron qildingiz.\n\n"
                "Adminlarga xabar yuborildi. Sizni kutib qolamiz!",
                parse_mode="HTML"
            )
            
            # 3. Adminga xabar yuboramiz
            user_name = message.from_user.full_name
            username = f"@{message.from_user.username}" if message.from_user.username else "Username yo'q"
            
            admin_text = (
                f"🚨 <b>WEB APP ORQALI YANGI BRON!</b>\n\n"
                f"👤 <b>Mijoz:</b> {user_name} ({username})\n"
                f"🖥 <b>Kompyuter:</b> {pc_number}"
            )
            await bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode="HTML")
            
        except Exception as e:
            await message.answer("⚠️ Kechirasiz, xarita orqali bron qilishda xatolik yuz berdi.")
            logging.error(f"Web App datani saqlash xatosi: {e}")

# --- TASDIQLASH VA BAZAGA YUBORISH ---
@dp.message(BookingState.waiting_for_confirmation, F.text.lower().in_(["ha", "hə", "yes", "ok", "bo'ladi"]))
async def confirm_booking(message: types.Message, state: FSMContext):
    data = await state.get_data()
    booking_info = data.get("booking_info")
    user_id = message.from_user.id
    
    try:
        # 0. AVVAL foydalanuvchini bazada borligini tekshiramiz va yo'q bo'lsa qo'shamiz!
        existing_user = supabase.table("users").select("*").eq("telegram_id", user_id).execute()
        if not existing_user.data:
            supabase.table("users").insert({
                "telegram_id": user_id,
                "full_name": message.from_user.full_name,
                "username": message.from_user.username
            }).execute()

        # 1. Endi ma'lumotni bemalol Supabase bazasiga saqlaymiz!
        booking_data = {
            "user_id": user_id,
            "booking_details": booking_info,
            "status": "pending"
        }
        supabase.table("bookings").insert(booking_data).execute()
        
        # 2. Mijozga javob qaytaramiz
        await message.answer(
            "🎉 <b>Ajoyib! Joyingiz muvaffaqiyatli bron qilindi va bazaga saqlandi.</b>\n\n"
            "Adminlarga xabar yuborildi. Sizni kutib qolamiz!", 
            parse_mode="HTML"
        )
        
        # 3. Adminga xabar yuboramiz
        user_name = message.from_user.full_name
        username = f"@{message.from_user.username}" if message.from_user.username else "Username yo'q"
        admin_text = (
            f"🚨 <b>YANGI BRON BAZAGA TUSHDI!</b>\n\n"
            f"👤 <b>Mijoz:</b> {user_name} ({username})\n"
            f"📋 <b>Tafsilotlar:</b>\n{booking_info}"
        )
        await bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode="HTML")
        
    except Exception as e:
        await message.answer("⚠️ Kechirasiz, bazaga saqlashda xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.")
        logging.error(f"Bazaga saqlash xatosi: {e}")
    
    await state.clear()

@dp.message(BookingState.waiting_for_confirmation)
async def cancel_booking(message: types.Message, state: FSMContext):
    await message.answer("❌ Bron bekor qilindi. Qaytadan ovozli xabar yuborib so'rashingiz mumkin.")
    await state.clear()

@dp.message(F.text)
async def echo_message(message: types.Message):
    await message.answer("Iltimos, bron qilish uchun ovozli xabar yuboring 🎙")

# --- RENDER UCHUN SOXTA (DUMMY) VEB SERVER ---
async def health_check(request):
    return web.Response(text="Bot muvaffaqiyatli ishlamoqda!")

async def main():
    # 1. Render talab qilgan portni ochamiz
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render o'zi beradigan portni olamiz, topolmasa 10000 ishlatamiz
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Soxta veb-server {port}-portda ishga tushdi...")
    
    # 2. Asosiy botimizni ishga tushiramiz
    logging.info("Telegram bot ishga tushmoqda...")
    await bot.delete_webhook(drop_pending_updates=True) # Sizning kodingiz saqlab qolindi
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot to'xtatildi.")