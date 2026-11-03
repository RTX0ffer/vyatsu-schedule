import datetime
import json
import logging
import os
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv('BOT_TOKEN', '')
TIMEZONE = ZoneInfo('Europe/Kirov')
CACHE_FILE = 'lessons_cache.json'
ICS_URL = os.getenv(
    'ICS_URL',
    'https://raw.githubusercontent.com/<YOUR_GITHUB_USERNAME>/<YOUR_REPO>/main/vyatsu.ics'
)

WEEKDAYS_RU = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']

dp = Dispatcher()


def load_lessons():
    """Считывает закэшированные уроки из файла."""
    if not os.path.exists(CACHE_FILE):
        return []
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return list(data.get('lessons', {}).values())
    except Exception as e:
        logging.error(f'Ошибка чтения кэша: {e}')
        return []


def format_day_schedule(target_date: datetime.date):
    """Форматирует расписание на конкретный день."""
    lessons = load_lessons()
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

    text = [f"📅 *{weekday_name}, {date_str}*\n"]
    for i, (start_dt, item) in enumerate(day_lessons, 1):
        end_dt = datetime.datetime.fromisoformat(item['end']).astimezone(TIMEZONE)
        time_interval = f"{start_dt.strftime('%H:%M')} – {end_dt.strftime('%H:%M')}"
        text.append(
            f"*{i}. {time_interval}* | {item['summary']}\n"
            f"   📍 _{item.get('location', 'ВятГУ')}_\n"
        )

    return "\n".join(text)


@dp.message(Command('start', 'help'))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я бот с актуальным расписанием занятий ВятГУ.\n\n"
        "Команды:\n"
        "▫️ /today — Пары на сегодня\n"
        "▫️ /tomorrow — Пары на завтра\n"
        "▫️ /week — Расписание на всю текущую неделю\n"
        "▫️ /calendar — Ссылка для подписки в календарь смартфона (iOS / Android)\n",
        parse_mode=ParseMode.MARKDOWN
    )


@dp.message(Command('today'))
async def cmd_today(message: types.Message):
    today = datetime.datetime.now(TIMEZONE).date()
    await message.answer(format_day_schedule(today), parse_mode=ParseMode.MARKDOWN)


@dp.message(Command('tomorrow'))
async def cmd_tomorrow(message: types.Message):
    tomorrow = datetime.datetime.now(TIMEZONE).date() + datetime.timedelta(days=1)
    await message.answer(format_day_schedule(tomorrow), parse_mode=ParseMode.MARKDOWN)


@dp.message(Command('week'))
async def cmd_week(message: types.Message):
    today = datetime.datetime.now(TIMEZONE).date()
    start_of_week = today - datetime.timedelta(days=today.weekday())

    blocks = []
    for day_offset in range(6):  # Пн-Сб
        day_date = start_of_week + datetime.timedelta(days=day_offset)
        blocks.append(format_day_schedule(day_date))

    response = "\n" + "—" * 20 + "\n\n".join(blocks)
    # Если сообщение слишком длинное для Telegram (лимит 4096 символов)
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
        "📲 *Как подписаться на календарь на телефоне:*\n\n"
        "1. **iPhone (Apple Calendar):**\n"
        "   Скопируйте ссылку ниже и вставьте в Safari или перейдите в:\n"
        "   _Настройки ➔ Календарь ➔ Учетные записи ➔ Добавить ➔ Подписной календарь_.\n"
        f"   Ссылка: `{webcal_url}`\n\n"
        "2. **Android / Google Календарь:**\n"
        "   Откройте [Google Calendar Web](https://calendar.google.com/) с компьютера ➔ Другие календари ➔ «+» ➔ «Добавить по URL».\n"
        f"   Ссылка: `{ICS_URL}`\n\n"
        "✨ Расписание будет обновляться на телефоне автоматически!",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb
    )


async def main():
    if not BOT_TOKEN:
        print("Ошибка: укажите токен бота в переменной окружения BOT_TOKEN!")
        return

    bot = Bot(token=BOT_TOKEN)
    await dp.start_polling(bot)


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
