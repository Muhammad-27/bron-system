import json
import logging
from aiogram import Router, types, F

# config.py dan kerakli ulanishlarni chaqirib olamiz
from config import supabase, bot, ADMIN_ID

# Xarita uchun alohida Router
web_app_router = Router()

# --- WEB APP DAN KELGAN MA'LUMOTNI USHLAB OLISH ---
@web_app_router.message(F.web_app_data)
async def web_app_handler(message: types.Message):
    # React'dan kelgan JSON ma'lumotni o'qiymiz
    data = message.web_app_data.data
    parsed_data = json.loads(data)
    
    action = parsed_data.get("action")
    pc_id = parsed_data.get("pc_id")
    pc_number = parsed_data.get("pc_number")
    
    if action == "book":
        try:
            # 1. BAZADAN MIJOZNING TELEFON RAQAMINI QIDIRIB OLAMIZ
            phone_number = "Noma'lum"
            user_info = supabase.table("users").select("phone").eq("telegram_id", message.from_user.id).execute()
            if user_info.data and user_info.data[0].get("phone"):
                phone_number = user_info.data[0]["phone"]

            # 2. Supabase bazasida kompyuterni "band" qilib qo'yamiz
            supabase.table("computers").update({
                "is_active": False,
                "booked_by": message.from_user.id
            }).eq("id", pc_id).execute()
            
            # 3. Mijozga xabar beramiz
            await message.answer(
                f"🎉 <b>Ajoyib!</b> Siz xarita orqali <b>{pc_number}</b> ni muvaffaqiyatli bron qildingiz.\n\n"
                "Adminlarga xabar yuborildi. Sizni kutib qolamiz!",
                parse_mode="HTML"
            )
            
            # 4. Adminga xabar yuboramiz (Xarita uchun)
            user_name = message.from_user.full_name
            username = f"@{message.from_user.username}" if message.from_user.username else "Username yo'q"
            
            admin_text = (
                f"🚨 <b>WEB APP ORQALI YANGI BRON!</b>\n\n"
                f"👤 <b>Mijoz:</b> {user_name} ({username})\n"
                f"📞 <b>Telefon:</b> {phone_number}\n"
                f"🖥 <b>Kompyuter:</b> {pc_number}"
            )
            await bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode="HTML")
            
        except Exception as e:
            await message.answer("⚠️ Kechirasiz, xarita orqali bron qilishda xatolik yuz berdi.")
            logging.error(f"Web App datani saqlash xatosi: {e}")