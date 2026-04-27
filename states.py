from aiogram.fsm.state import State, StatesGroup

class BookingState(StatesGroup):
    waiting_for_confirmation = State()

# --- ADMIN UCHUN HOLATLAR ---
class AdminState(StatesGroup):
    waiting_for_pc_selection = State() # Kompyuterni tanlashini kutish
    waiting_for_new_price = State()  # Yangi narx yozishini kutish
    waiting_for_cancel_id = State()