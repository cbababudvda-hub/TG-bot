import asyncio
import json
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# Ваши данные
BOT_TOKEN = "9113562453:AAEFI6PBDFThQW8ZIqpB0dK7PLrXxyYiIhQ"
GROUP_ID = -1002392676323
TOPIC_ID_REQUESTS = 4188
TOPIC_ID_TABLE = 4196

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
DATA_FILE = "bot_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"table_message_id": None, "requests": []}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_amount(building_type):
    building_type = building_type.lower().strip()
    if "высокая" in building_type: return 350000
    elif "средняя" in building_type: return 150000
    return 0

def generate_table_text(requests):
    now = datetime.now()
    year, month = now.year, now.month
    month_names = ["января", "февраля", "марта", "апреля", "мая", "июня", 
                   "июля", "августа", "сентября", "октября", "ноября", "декабря"]
    
    daily_totals = {}
    for req in requests:
        day = req["day"]
        daily_totals[day] = daily_totals.get(day, 0) + req["amount"]
    
    lines = []
    total_month = 0
    for day in range(1, 32):
        date_str = f"{day:02d}.{month:02d}.{str(year)[2:]}"
        if day in daily_totals:
            amount = daily_totals[day]
            lines.append(f"{date_str} – {amount:,}₽".replace(",", "."))
            total_month += amount
        else:
            lines.append(f"{date_str} –")
    
    lines.append("")
    lines.append(f"Сумма за {month_names[month-1]} {year} года: {total_month:,}₽".replace(",", "."))
    return "\n".join(lines)

@dp.message(Command("start_month"))
async def cmd_start_month(message: types.Message):
    if message.chat.id != GROUP_ID: return
    data = load_data()
    data["requests"] = []
    table_text = generate_table_text([])
    sent_message = await bot.send_message(chat_id=GROUP_ID, text=table_text, message_thread_id=TOPIC_ID_TABLE)
    data["table_message_id"] = sent_message.message_id
    save_data(data)
    await message.reply("✅ Таблица на этот месяц создана!")

@dp.message(Command("update"))
async def cmd_update(message: types.Message):
    if message.chat.id != GROUP_ID: return
    data = load_data()
    if data["table_message_id"] is None:
        await message.reply("❌ Сначала создайте таблицу командой /start_month"); return
    table_text = generate_table_text(data["requests"])
    try:
        await bot.edit_message_text(chat_id=GROUP_ID, message_id=data["table_message_id"], text=table_text, message_thread_id=TOPIC_ID_TABLE)
        await message.reply("✅ Таблица обновлена!")
    except Exception as e: await message.reply(f"❌ Ошибка: {e}")

@dp.message(Command("total"))
async def cmd_total(message: types.Message):
    if message.chat.id != GROUP_ID: return
    data = load_data()
    if data["table_message_id"] is None: return
    total = sum(req["amount"] for req in data["requests"])
    await message.reply(f"💰 Итого за месяц: {total:,}₽".replace(",", "."))
    data["requests"] = []
    table_text = generate_table_text([])
    try:
        await bot.edit_message_text(chat_id=GROUP_ID, message_id=data["table_message_id"], text=table_text, message_thread_id=TOPIC_ID_TABLE)
        save_data(data)
        await message.reply("✅ Таблица очищена!")
    except Exception as e: await message.reply(f"❌ Ошибка: {e}")

@dp.message()
async def handle_message(message: types.Message):
    if message.chat.id != GROUP_ID: return
    if message.message_thread_id != TOPIC_ID_REQUESTS: return
    text = message.text or ""
    if "Тип стройки" not in text: return
    
    lines = text.split("\n")
    building_type = None
    for line in lines:
        if "Тип стройки" in line:
            parts = line.split(":")
            if len(parts) > 1:
                building_type = parts[1].strip(); break
    if not building_type: return
    
    amount = get_amount(building_type)
    if amount == 0: return
    
    data = load_data()
    data["requests"].append({"day": datetime.now().day, "amount": amount, "type": building_type})
    save_data(data)
    await message.reply(f"✅ Заявка добавлена: {amount:,}₽".replace(",", "."))

async def on_startup():
    webhook_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/webhook"
    await bot.set_webhook(webhook_url)
    print(f"Webhook установлен на: {webhook_url}")

async def main():
    await on_startup()
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
    setup_application(app, dp, bot=bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 8080)))
    await site.start()
    print("Бот работает на Render!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
