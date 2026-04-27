import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Ulanishlar va Holatlarni chaqiramiz
from config import supabase, ADMIN_ID
from states import AdminState

# Admin uchun alohida Router
admin_router = Router()

# Admin ekanligini tekshirish uchun kichik yordamchi qorovul (Funksiya)
def is_admin(user_id):
    return str(user_id) == str(ADMIN_ID)

# --- 1. ADMIN PANELGA KIRISH (/admin) ---
@admin_router.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    # Begonalar kirmasligi uchun himoya
    if not is_admin(message.from_user.id):
        await message.answer("Kechirasiz, sizda bu buyruqdan foydalanish huquqi yo'q. ❌")
        return
        
    await state.clear() # Har ehtimolga qarshi tozalab yuboramiz
    
    # Admin tugmalari
    kb = [
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="💻 Kompyuterlar")],
        [KeyboardButton(text="❌ Faol bronlar")]
    ]
    markup = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    
    await message.answer(
        "👨‍💻 <b>Admin Panelga xush kelibsiz, Xo'jayin!</b>\n\nNimani boshqaramiz?", 
        reply_markup=markup, 
        parse_mode="HTML"
    )

# --- 2. STATISTIKA QISMI ---
@admin_router.message(F.text == "📊 Statistika")
async def show_statistics(message: types.Message):
    if not is_admin(message.from_user.id):
        return
        
    wait_msg = await message.answer("⏳ Ma'lumotlar bazadan yig'ilmoqda...")
    
    try:
        # 1. Mijozlar sonini hisoblash
        users = supabase.table("users").select("id", count="exact").execute()
        total_users = users.count if users.count else 0
        
        # 2. Ovozli bronlar sonini hisoblash
        bookings = supabase.table("bookings").select("id", count="exact").execute()
        total_bookings = bookings.count if bookings.count else 0
        
        # 3. Xaritada hozir band bo'lib turgan kompyuterlarni hisoblash
        pcs = supabase.table("computers").select("id").eq("is_active", False).execute()
        booked_pcs = len(pcs.data) if pcs.data else 0
        
        text = (
            "📊 <b>Klubning joriy statistikasi:</b>\n\n"
            f"👥 <b>Jami ro'yxatdan o'tgan mijozlar:</b> {total_users} ta\n"
            f"📝 <b>AI orqali qilingan jami bronlar:</b> {total_bookings} ta\n"
            f"🖥 <b>Hozir band kompyuterlar (Xaritadan):</b> {booked_pcs} ta\n"
        )
        await wait_msg.edit_text(text, parse_mode="HTML")
        
    except Exception as e:
        await wait_msg.edit_text("❌ Ma'lumotlarni olishda xatolik yuz berdi.")
        logging.error(f"Statistika xatosi: {e}")
        
# --- 3. FAOL BRONLARNI BEKOR QILISH (Uzluksiz rejim) ---
@admin_router.message(F.text == "❌ Faol bronlarni bekor qilish")
async def cancel_bookings_menu(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.clear()
    
    bookings = supabase.table("bookings").select("*").eq("status", "pending").execute()
    
    if not bookings.data:
        await message.answer("✅ Hozircha bekor qilish uchun faol yoki kutilayotgan bronlar yo'q.")
        return
        
    text = "❌ <b>Bekor qilinishi mumkin bo'lgan bronlar:</b>\n\n"
    for b in bookings.data:
        text += f"🆔 <b>ID:</b> {b['id']}\n"
        text += f"📝 <b>Tafsilot:</b> {b['booking_details']}\n"
        text += "━━━━━━━━━━━━━━\n"
        
    await message.answer(text, parse_mode="HTML")
    await message.answer("O'chirish uchun bronning <b>ID raqamini</b> yozing (masalan: 12):\n\n<i>Jarayonni to'xtatish uchun <b>chiqish</b> deb yozing yoki pastdagi menyu tugmalaridan birini bosing.</i>", parse_mode="HTML")
    await state.set_state(AdminState.waiting_for_cancel_id)

@admin_router.message(AdminState.waiting_for_cancel_id)
async def process_cancel_id(message: types.Message, state: FSMContext):
    booking_id = message.text.lower()
    
    # Agar chiqish desa, holatni tozalaymiz
    if booking_id == "chiqish":
        await message.answer("🚫 O'chirish jarayoni to'xtatildi.")
        await state.clear()
        return
        
    # Agar raqam yozmasa
    if not booking_id.isdigit():
        await message.answer("⚠️ Iltimos, faqat bronning ID raqamini yozing yoki 'chiqish' deb yozing.")
        return

    try:
        supabase.table("bookings").update({"status": "cancelled"}).eq("id", int(booking_id)).execute()
        await message.answer(f"✅ <b>{booking_id}-ID</b> dagi bron muvaffaqiyatli bekor qilindi!\n\nYana o'chirmoqchi bo'lsangiz navbatdagi ID ni yozing, bo'lmasa <b>chiqish</b> deb yozing.", parse_mode="HTML")
        # DIQQAT: Bu yerda state.clear() QILINMAYDI. Shuning uchun admin to chiqish demaguncha o'chiraveradi!
    except Exception as e:
        await message.answer("❌ Xatolik yuz berdi. ID ni to'g'ri yozganingizga ishonch hosil qiling.")


# --- 4. KOMPYUTERLAR BOSHQARUVI (Narx va Holat) ---
@admin_router.message(F.text == "💻 Kompyuterlar")
async def computers_menu(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.clear()
    
    pcs = supabase.table("computers").select("*").order("id").execute()
    
    text = "💻 <b>Kompyuterlar ro'yxati:</b>\n\n"
    if pcs.data:
        for pc in pcs.data:
            status = "🟢 Bo'sh" if pc['is_active'] else "🔴 Band"
            price = pc.get('price_per_hour', 'Belgilanmagan') 
            text += f"🖥 <b>{pc['pc_number']}</b> | {status} | 💰 {price} so'm\n"
    
    await message.answer(text, parse_mode="HTML")
    # Tushunarliroq qilish uchun o'zgartirdik:
    await message.answer("Tahrirlash uchun kompyuter nomini to'liq yozing (masalan: <b>PC-1</b> yoki <b>VIP-1</b>):\n\n<i>Jarayonni to'xtatish uchun <b>chiqish</b> deb yozing.</i>", parse_mode="HTML")
    await state.set_state(AdminState.waiting_for_pc_selection)

@admin_router.message(AdminState.waiting_for_pc_selection)
async def process_pc_selection(message: types.Message, state: FSMContext):
    # Harflarni avtomatik KATTA qilib olamiz (pc-1 yozsa ham PC-1 bo'ladi)
    pc_number = message.text.upper() 
    
    if pc_number == "CHIQISH":
        await message.answer("🚫 Tahrirlash to'xtatildi.")
        await state.clear()
        return
        
    # BAZADAN TEKSHIRAMIZ (Shunday kompyuter rostdan bormi?)
    check_pc = supabase.table("computers").select("id").eq("pc_number", pc_number).execute()
    if not check_pc.data:
        await message.answer(f"⚠️ <b>{pc_number}</b> nomli kompyuter topilmadi! Iltimos, ro'yxatda qanday yozilgan bo'lsa shunday yozing (masalan: PC-1).")
        return # Agar topmasa, pastga o'tkazmaymiz!

    await state.update_data(selected_pc=pc_number)
    await message.answer(
        f"🖥 <b>{pc_number}-kompyuter tanlandi!</b>\n\n"
        f"💰 Narxni o'zgartirish uchun <b>yangi narxni raqamlarda</b> yozing (masalan: 20000)\n"
        f"🟢 Kompyuterni bo'shatish (banddan yechish) uchun <b>bosh</b> deb yozing.",
        parse_mode="HTML"
    )
    await state.set_state(AdminState.waiting_for_new_price)
    
@admin_router.message(AdminState.waiting_for_new_price)
async def process_new_price(message: types.Message, state: FSMContext):
    new_val = message.text.lower()
    if new_val == "chiqish":
        await message.answer("🚫 Tahrirlash to'xtatildi.")
        await state.clear()
        return

    data = await state.get_data()
    pc_number = data.get("selected_pc") # Bu hozir "PC-1" holatida turibdi
    
    try:
        if new_val == "bosh":
            # Endi aniq topadi!
            supabase.table("computers").update({"is_active": True, "booked_by": None}).eq("pc_number", pc_number).execute()
            await message.answer(f"✅ <b>{pc_number}</b> muvaffaqiyatli bo'shatildi!", parse_mode="HTML")
        else:
            if not new_val.isdigit():
                await message.answer("⚠️ Iltimos, narxni faqat raqamlarda yozing.")
                return
            supabase.table("computers").update({"price_per_hour": int(new_val)}).eq("pc_number", pc_number).execute()
            await message.answer(f"✅ <b>{pc_number}</b> narxi {new_val} so'mga o'zgardi!", parse_mode="HTML")
            
    except Exception as e:
        await message.answer("❌ Bazaga saqlashda xatolik yuz berdi.")
        
    await state.clear()