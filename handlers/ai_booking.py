import os
import logging
from aiogram import Router, types, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

# Ulanishlar va Holatlar (States) ni chaqiramiz
from config import ai_client, bot, supabase, ADMIN_ID
from states import BookingState

# AI va ovozli xabarlar uchun alohida Router
ai_router = Router()

# --- 1. OVOZ VA MATNNI TUSHUNADIGAN AI AGENT ---
@ai_router.message(StateFilter(None), F.voice | F.text)
async def handle_voice_or_text(message: types.Message, state: FSMContext):
    
    # 🛑 ADMIN UCHUN AI NI TO'LIQ BLOKLASH
    if str(message.from_user.id) == str(ADMIN_ID):
        return

    # Agar xabar "/" bilan boshlansa yoki menyu tugmalari bosilsa, AI o'qimaydi
    if message.text and (message.text.startswith("/") or message.text in ["📋 Mening bronlarim", "📱 Telefon raqamni yuborish", "🖥 Klub xaritasi"]):
        return

    wait_msg = await message.answer("⏳ Ma'lumot qabul qilindi. Tahlil qilinmoqda...")
    # ... (qolgan kodlar o'zgarishsiz qoladi)

    try:
        recognized_text = ""
        # ... qolgan kodlar o'zgarishsiz qoladi ...
        
        # Agar xabar OVOZLI bo'lsa
        if message.voice:
            voice_id = message.voice.file_id
            file = await bot.get_file(voice_id)
            os.makedirs("temp", exist_ok=True)
            downloaded_file = f"temp/{voice_id}.ogg"
            await bot.download_file(file.file_path, downloaded_file)
            
            with open(downloaded_file, "rb") as audio_file:
                transcription = await ai_client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=audio_file,
                    prompt="Assalomu alaykum. Menga kompyuter kerak. Bugun soat 20:00 dan 22:00 gacha 3 ta joy bron qilmoqchiman. Yonma-yon bo'lsin. Ikkita, uchta, to'rtta, beshta. Ertalab, kechqurun, abedda. Komp, zanet, qilib ber, aka."
                )
            recognized_text = transcription.text
            os.remove(downloaded_file) # Faylni darhol o'chiramiz
            
        # Agar xabar YOZUV (Matn) bo'lsa
        elif message.text:
            recognized_text = message.text

     # --- AI ga jo'natamiz ---
        gpt_response = await ai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system", 
                    "content": (
                        "Siz kompyuter klubining aqlli va xushmuomala yordamchisisiz. Mijozning maqsadini aniqlang.\n\n"
                        "1-QOIDA (BRON QILISH): Agar mijoz aniq joy bron qilmoqchi bo'lsa (vaqt, soat yoki kompyuter haqida gapirsa), javobni qat'iy 'BRON:' so'zi bilan boshlang va quyidagi formatda bering:\n"
                        "BRON:\n"
                        "Boshlanish vaqti: [vaqt]\n"
                        "Tugash vaqti: [vaqt yoki Aytilmagan]\n"
                        "Kompyuterlar soni: [soni yoki 1 ta]\n"
                        "Izoh: [VIP/yonma-yon yoki Ixtiyoriy]\n\n"
                        "2-QOIDA (ODDIY SUHBAT): Agar mijoz shunchaki salomlashsa, savol bersa (narxlar qancha, qayerdasiz, qanday o'yinlar bor) yoki bron qilish niyati aniq bo'lmasa, 'BRON:' so'zini umuman ishlatmang! Javobni 'SUHBAT:' so'zi bilan boshlab, do'stona va qisqa javob qaytaring.\n"
                        "Masalan: 'SUHBAT: Assalomu alaykum! Klubimizga xush kelibsiz. Bizda narxlar soatiga 15,000 so'm. Joy band qilishni xohlaysizmi?'"
                    )
                },
                {"role": "user", "content": recognized_text}
            ],
            temperature=0.3
        )
        
        parsed_data = gpt_response.choices[0].message.content.strip()

        # --- JAVOBNI TEKSHIRAMIZ VA IKKIGA AJRATAMIZ ---
        
        # 1-Holat: Agar AI mijoz faqat gaplashmoqchi ekanligini tushunsa
        if parsed_data.startswith("SUHBAT:"):
            clean_reply = parsed_data.replace("SUHBAT:", "").strip()
            await wait_msg.edit_text(clean_reply)
            return # Dasturni shu yerda to'xtatamiz, bot "Tasdiqlash" rejimiga kirmaydi!

        # 2-Holat: Agar AI aniq bronni tushunsa
        elif parsed_data.startswith("BRON:"):
            clean_reply = parsed_data.replace("BRON:", "").strip()
            
            # State ga saqlaymiz va tasdiq kutamiz
            await state.update_data(booking_info=clean_reply)
            await state.set_state(BookingState.waiting_for_confirmation)

            final_message = (
                f"🤖 <b>AI agent tushungan ma'lumot:</b>\n\n"
                f"{clean_reply}\n\n"
                f"✅ Hammasi to'g'rimi? (Tasdiqlash uchun <b>ha</b> deb yozing)"
            )
            await wait_msg.edit_text(final_message, parse_mode="HTML")
            
        # 3-Holat: AI adashib boshqa narsa yuborsa (Himoya)
        else:
            await wait_msg.edit_text("Kechirasiz, xabaringizni to'liq tushuna olmadim. Iltimos, bron qilish maqsadingizni aniqroq yozing.")

    except Exception as e:
        await wait_msg.edit_text("❌ Tizimda kichik nosozlik yuz berdi. Iltimos, qayta urinib ko'ring.")
        logging.error(f"AI xatosi: {e}")

# --- 2. TASDIQLASH QADAMI ("Ha" yoki "Yo'q") ---
@ai_router.message(BookingState.waiting_for_confirmation)
async def confirm_booking(message: types.Message, state: FSMContext):
    
    user_reply = message.text.lower() if message.text else ""
    
    # Agar "ha" desa (barcha variantlarni qo'shib ketdik: xa, yes)
    if user_reply in ["ha", "h", "yes", "xa"]:
        data = await state.get_data()
        ai_response_text = data.get("booking_info", "Noma'lum")
        
        # Raqamni olamiz
        phone_number = "Noma'lum"
        try:
            user_info = supabase.table("users").select("phone").eq("telegram_id", message.from_user.id).execute()
            if user_info.data and user_info.data[0].get("phone"):
                phone_number = user_info.data[0]["phone"]
        except Exception as e:
            logging.error(f"Raqamni olishda xatolik: {e}")

        # Bazaga yozamiz
        try:
            booking_data = {
                "user_id": message.from_user.id,
                "booking_details": ai_response_text,
                "status": "pending"
            }
            supabase.table("bookings").insert(booking_data).execute()
            
            await message.answer("🎉 Ajoyib! Joyingiz muvaffaqiyatli bron qilindi va bazaga saqlandi.\n\nAdminlarga xabar yuborildi. Sizni kutib qolamiz!")

            # Adminga xabar
            admin_message = (
                f"🚨 <b>YANGI BRON BAZAGA TUSHDI! (AI orqali)</b>\n\n"
                f"👤 <b>Mijoz:</b> {message.from_user.full_name} (@{message.from_user.username})\n"
                f"📞 <b>Telefon:</b> {phone_number}\n"
                f"📋 <b>Tafsilotlar:</b>\n{ai_response_text}"
            )
            await bot.send_message(chat_id=ADMIN_ID, text=admin_message, parse_mode="HTML")
            
        except Exception as e:
            await message.answer("❌ Bazaga saqlashda xatolik yuz berdi.")
            logging.error(f"Insert xatosi: {e}")
            
        # Jarayonni yakunlaymiz
        await state.clear()
        
    # Agar "yo'q" desa
    elif user_reply in ["yo'q", "yoq", "y", "no"]:
        await message.answer("❌ Bron bekor qilindi. Boshqa vaqt yoki kompyuter kerak bo'lsa bemalol yozishingiz mumkin.")
        await state.clear()
        
    # Tushunarsiz narsa yozsa
    else:
        await message.answer("Iltimos, tasdiqlash uchun <b>ha</b> yoki bekor qilish uchun <b>yo'q</b> deb yozing.", parse_mode="HTML")