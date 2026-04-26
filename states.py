from aiogram.fsm.state import State, StatesGroup

class BookingState(StatesGroup):
    waiting_for_confirmation = State()