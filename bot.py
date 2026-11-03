import asyncio
import datetime
import json
import logging
import os
import time
from zoneinfo import ZoneInfo

import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiohttp import web

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

BOT_TOKEN = os.getenv('BOT_TOKEN', '')
TIMEZONE = ZoneInfo('Europe/Kirov')
CACHE_FILE = 'lessons_cache.json'

# Ссылка на JSON в репозитории на GitHub (укажите в переменных окружения на хостинге)
DATA_URL = os.getenv('DATA_URL', '')
ICS_URL = os.getenv(
    'ICS_URL',
    'https://raw.githubusercontent.com/<YOUR_GITHUB_USERNAME>/<YOUR_REPO>/main/vyatsu.ics'
)

WEEKDAYS_RU = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']

dp = Dispatcher()

# Локальный кэш уроков в оперативной памяти с временем жизни (TTL)
_memory_cache = {'timestamp': 0, 'lessons': []}
CACHE_TTL = 1800  # 30 минут


async def load_lessons():
    """Считывает уроки из GitHub Raw или локального файла с кэшированием в ОЗУ."""
    now = time.time()
    if _memory_cache['lessons'] and (now - _memory_cache['timestamp'] < CACHE_TTL):
        return _memory_cache['lessons']

    # 1. Если задан DATA_URL, пытаемся скачать свежий JSON с GitHub
    if DATA_URL:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(DATA_URL, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        lessons = list(data.get('lessons', {}).values())
                        _memory_cache['lessons'] = lessons
                        _memory_cache['timestamp'] = now
                        logging.info(f'Загружено {len(lessons)} пар из удаленного репозитория.')
                        return lessons
        except Exception as e:
            logging.error(f'Ошибка загрузки с GitHub ({DATA_URL}): {e}')

    # 2. Фолбэк на локальный файл (если есть)
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                lessons = list(data.get('lessons', {}).values())
                _memory_cache['lessons'] = lessons
                _memory_cache['timestamp'] = now
                return lessons
        except Exception as e:
            logging.error(f'Ошибка чтения локального кэша: {e}')

    return _memory_cache['lessons']


async def format_day_schedule(target_date: datetime.date):
    """Форматирует расписание на конкретный день с группировкой по времени."""
    lessons = await load_lessons()
    day_lessons = []

    for item in lessons:
        start_dt = datetime.datetime.fromisoformat(item['start']).astimezone(TIMEZONE)
        if start_dt.date() == target_date:
            day_lessons.append((start_dt, item))

    day_lessons.sort(key=lambda x: x[0])

    weekday_name = WEEKDAYS_RU[target_date.weekday()]
    date_str = target_date.strftime('%d.%m.%Y')

    if not day_lessons:
        return f"📅 *{weekday_name}, {date_str}*\n\n🎉 В этот день пар нет! Можно отдыхать."

    # Группируем пары по временному интервалу (чтобы подгруппы шли одним блоком)
    by_time = {}
    for start_dt, item in day_lessons:
        end_dt = datetime.datetime.fromisoformat(item['end']).astimezone(TIMEZONE)
        interval = f"{start_dt.strftime('%H:%M')} – {end_dt.strftime('%H:%M')}"
        by_time.setdefault(interval, []).append(item)

    text = [f"📅 *{weekday_name}, {date_str}*\n"]
    for interval, items in by_time.items():
        if len(items) == 1:
            it = items[0]
            text.append(
                f"▫️ *{interval}* | {it['summary']}\n"
                f"   📍 _{it.get('location', 'ВятГУ')}_\n"
            )
        else:
            text.append(f"▫️ *{interval}*:")
            for it in items:
                text.append(
                    f"   • {it['summary']}\n"
                    f"     📍 _{it.get('location', 'ВятГУ')}_"
                )
            text.append("")

    return "\n".join(text).strip()


@dp.message(Command('start', 'help'))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я бот с расписанием занятий ВятГУ.\n\n"
        "Команды:\n"
        "▫️ /today — Пары на сегодня\n"
        "▫️ /tomorrow — Пары на завтра\n"
        "▫️ /week — Расписание на текущую неделю\n"
        "▫️ /calendar — Ссылка для подписки в календарь смартфона (iOS / Android)\n",
        parse_mode=ParseMode.MARKDOWN
    )


@dp.message(Command('today'))
async def cmd_today(message: types.Message):
    today = datetime.datetime.now(TIMEZONE).date()
    text = await format_day_schedule(today)
    await message.answer(text, parse_mode=ParseMode.MARKDOWN)


@dp.message(Command('tomorrow'))
async def cmd_tomorrow(message: types.Message):
    tomorrow = datetime.datetime.now(TIMEZONE).date() + datetime.timedelta(days=1)
    text = await format_day_schedule(tomorrow)
    await message.answer(text, parse_mode=ParseMode.MARKDOWN)


@dp.message(Command('week'))
async def cmd_week(message: types.Message):
    today = datetime.datetime.now(TIMEZONE).date()
    start_of_week = today - datetime.timedelta(days=today.weekday())

    blocks = []
    for day_offset in range(6):  # Пн-Сб
        day_date = start_of_week + datetime.timedelta(days=day_offset)
        blocks.append(await format_day_schedule(day_date))

    separator = "\n\n" + "—" * 20 + "\n\n"
    response = separator.join(blocks)

    if len(response) > 4000:
        for chunk in [response[i:i + 3800] for i in range(0, len(response), 3800)]:
            await message.answer(chunk, parse_mode=ParseMode.MARKDOWN)
    else:
        await message.answer(response, parse_mode=ParseMode.MARKDOWN)


@dp.message(Command('calendar'))
async def cmd_calendar(message: types.Message):
    webcal_url = ICS_URL.replace('https://', 'webcal://')
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="📅 Добавить в календарь", url=ICS_URL)]]
    )
    await message.answer(
        "📲 *Как подписаться на календарь на смартфоне:*\n\n"
        "1. **iPhone (Apple Calendar):**\n"
        "   Вставьте в Safari ссылку:\n"
        f"   `{webcal_url}`\n\n"
        "2. **Android / Google Календарь:**\n"
        "   В [Google Calendar](https://calendar.google.com/) нажмите *«+» ➔ «Добавить по URL»*:\n"
        f"   `{ICS_URL}`\n\n"
        "Расписание синхронизируется на телефоне автоматически!",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb
    )


# Простой HTTP-эндпоинт для прохождения health check на бесплатных хостингах (Render, Koyeb)
async def handle_ping(request):
    return web.Response(text="Bot is running!")


async def start_webserver():
    port = int(os.getenv('PORT', 8080))
    app = web.Application()
    app.router.add_get('/', handle_ping)
    app.router.add_get('/healthz', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Веб-сервер запущен на порту {port}")


async def main():
    if not BOT_TOKEN:
        logging.error("Не указан BOT_TOKEN в переменных окружения!")
        return

    # Запускаем одновременно HTTP-сервер и long-polling бота
    await start_webserver()
    bot = Bot(token=BOT_TOKEN)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
