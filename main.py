import asyncio
import logging
import os
from aiohttp import web

# O'zimiz yaratgan fayllardan kerakli narsalarni chaqiramiz
from config import bot, dp
from handlers import basic_router, web_app_router, ai_router ,admin_router

# --- RENDER UCHUN SOXTA (DUMMY) VEB SERVER ---
async def health_check(request):
    return web.Response(text="Bot muvaffaqiyatli ishlamoqda! Tizim 100% toza arxitekturada. 🚀")

async def main():
    # 1. Barcha Routerlarni (mantiqlarni) Asosiy Dispatcher'ga ulaymiz
    dp.include_router(basic_router)
    dp.include_router(web_app_router)
    dp.include_router(admin_router)
    dp.include_router(ai_router)

    # 2. Render talab qilgan portni ochamiz (Web Server)
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Soxta veb-server {port}-portda ishga tushdi...")
    
    # 3. Asosiy Telegram botimizni ishga tushiramiz
    logging.info("Telegram bot ishga tushmoqda...")
    await bot.delete_webhook(drop_pending_updates=True) # Qotib qolgan eskirgan xabarlarni o'chiradi
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot to'xtatildi.")