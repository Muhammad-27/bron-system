import logging
from aiogram import Router, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

# Ulanishlarni config.py dan chaqirib olamiz
from config import supabase

# Bu fayl uchun alohida Router ochamiz
basic_router = Router()

# --- 1. START BUYRUG'I (Faqat raqam so'raymiz) ---
@basic_router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear() # Har qanday chala qolgan amalni tozalaymiz
    
    kb = [
        [KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]
    ]
    markup = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True)
    
    await message.answer(
        f"Assalomu alaykum, <b>{message.from_user.full_name}</b>!\n\n"
        "Game Club botiga xush kelibsiz. Botdan foydalanish va kompyuter band qilish uchun, "
        "iltimos, pastdagi tugmani bosib telefon raqamingizni tasdiqlang.",
        reply_markup=markup,
        parse_mode="HTML"
    )

# --- 2. RAQAMNI QABUL QILIB, BAZAGA YOZISH VA ASOSIY MENYUNI OCHISH ---
@basic_router.message(F.contact)
async def handle_contact(message: types.Message):
    phone_number = message.contact.phone_number
    user_id = message.from_user.id
    
    # 1. Mijozni bazaga saqlaymiz yoki yangilaymiz
    user_data = {
        "telegram_id": user_id,
        "full_name": message.from_user.full_name,
        "username": message.from_user.username,
        "phone": phone_number
    }
    
    try:
        existing_user = supabase.table("users").select("*").eq("telegram_id", user_id).execute()
        if not existing_user.data:
            supabase.table("users").insert(user_data).execute()
        else:
            supabase.table("users").update({"phone": phone_number}).eq("telegram_id", user_id).execute()
    except Exception as e:
        logging.error(f"Bazaga yozishda xatolik: {e}")

    # 2. Xarita va Bronlarim tugmalarini yaratamiz
    web_app_url = "https://voluble-baklava-a461f1.netlify.app/" 
    
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🖥 Klub xaritasi", web_app=WebAppInfo(url=web_app_url))],
            [KeyboardButton(text="📋 Mening bronlarim")]
        ],
        resize_keyboard=True
    )

    await message.answer(
        f"✅ Rahmat! Raqamingiz qabul qilindi.\n\n"
        "Endi ovozli/matnli xabar yuborish orqali yoki pastdagi xaritadan joy tanlashingiz mumkin:",
        reply_markup=markup
    )

# --- 3. MENING BRONLARIM TUGMASI ---
@basic_router.message(F.text == "📋 Mening bronlarim")
async def my_bookings_handler(message: types.Message):
    user_id = message.from_user.id
    text = "<b>📋 Sizning faol bronlaringiz:</b>\n\n"
    has_bookings = False
    
    # Xaritadan qilingan bronlar (computers jadvali)
    try:
        pc_response = supabase.table("computers").select("*").eq("booked_by", user_id).eq("is_active", False).execute()
        if pc_response.data:
            for pc in pc_response.data:
                text += f"🖥 <b>Kompyuter:</b> {pc['pc_number']}\n"
                text += f"💰 <b>Narxi:</b> {pc['price']} so'm/soat\n"
                text += f"🟢 <b>Holati:</b> Tasdiqlangan\n"
                text += f"━━━━━━━━━━━━━━\n"
                has_bookings = True
    except Exception as e:
        logging.error(f"Kompyuter jadvalidan o'qishda xatolik: {e}")

    # Ovozli/matnli bronlar (bookings jadvali)
    try:
        voice_response = supabase.table("bookings").select("*").eq("user_id", user_id).execute()
        if voice_response.data:
            for b in voice_response.data:
                text += f"🎤 <b>AI Orqali bron:</b>\n"
                text += f"📝 <b>Tafsilot:</b> {b['booking_details']}\n"
                status_emoji = "⏳ Kutilyapti (Adminga yuborilgan)" if b['status'] == 'pending' else "✅ Tasdiqlangan"
                text += f"📊 <b>Holati:</b> {status_emoji}\n"
                text += f"━━━━━━━━━━━━━━\n"
                has_bookings = True
    except Exception as e:
        logging.error(f"Bookings jadvalidan o'qishda xatolik: {e}")

    if not has_bookings:
        await message.answer("Sizda hozircha faol bronlar yo'q. 🤷‍♂️")
    else:
        await message.answer(text, parse_mode="HTML")