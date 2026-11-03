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
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp, WebAppInfo
from aiohttp import web
from ics import Calendar, Event

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

BOT_TOKEN = os.getenv('BOT_TOKEN', '')
TIMEZONE = ZoneInfo('Europe/Kirov')
CACHE_FILE = 'lessons_cache.json'

DATA_URL = os.getenv('DATA_URL', '')
WEBAPP_URL = os.getenv('WEBAPP_URL', '').rstrip('/')
ICS_URL = os.getenv(
    'ICS_URL',
    f"{WEBAPP_URL}/calendar.ics" if WEBAPP_URL else 'https://raw.githubusercontent.com/<YOUR_GITHUB_USERNAME>/<YOUR_REPO>/main/vyatsu.ics'
)

WEEKDAYS_RU = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']

dp = Dispatcher()

_memory_cache = {'timestamp': 0, 'lessons': []}


def get_cached_lessons():
    """Синхронно и мгновенно возвращает пары из памяти или локального файла (0 мс)."""
    if _memory_cache['lessons']:
        return _memory_cache['lessons']

    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                lessons = list(data.get('lessons', {}).values())
                if lessons:
                    _memory_cache['lessons'] = lessons
                    _memory_cache['timestamp'] = time.time()
                    logging.info(f'Мгновенно загружено {len(lessons)} пар из локального файла.')
                    return lessons
        except Exception as e:
            logging.error(f'Ошибка чтения локального файла: {e}')

    return []


async def sync_remote_cache():
    """Фоновая асинхронная проверка обновлений с GitHub."""
    if not DATA_URL:
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(DATA_URL, timeout=8) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    lessons = list(data.get('lessons', {}).values())
                    if lessons:
                        _memory_cache['lessons'] = lessons
                        _memory_cache['timestamp'] = time.time()
                        logging.info(f'Фоновое обновление: загружено {len(lessons)} пар с GitHub.')
    except Exception as e:
        logging.warning(f'Фоновое обновление с GitHub не удалось: {e}')


async def background_cache_worker():
    """Периодически раз в 20 минут в фоне обновляет кэш."""
    while True:
        await asyncio.sleep(1200)
        await sync_remote_cache()


def format_day_schedule(target_date: datetime.date):
    """Форматирует расписание на день в безопасном формате HTML."""
    lessons = get_cached_lessons()
    day_lessons = []

    for item in lessons:
        start_dt = datetime.datetime.fromisoformat(item['start']).astimezone(TIMEZONE)
        if start_dt.date() == target_date:
            day_lessons.append((start_dt, item))

    day_lessons.sort(key=lambda x: x[0])

    weekday_name = WEEKDAYS_RU[target_date.weekday()]
    date_str = target_date.strftime('%d.%m.%Y')

    if not day_lessons:
        return f"📅 <b>{weekday_name}, {date_str}</b>\n\n🎉 В этот день пар нет! Можно отдыхать."

    by_time = {}
    for start_dt, item in day_lessons:
        end_dt = datetime.datetime.fromisoformat(item['end']).astimezone(TIMEZONE)
        interval = f"{start_dt.strftime('%H:%M')} – {end_dt.strftime('%H:%M')}"
        by_time.setdefault(interval, []).append(item)

    text = [f"📅 <b>{weekday_name}, {date_str}</b>\n"]
    for interval, items in by_time.items():
        if len(items) == 1:
            it = items[0]
            subj = it.get('subject', it.get('summary', 'Пара'))
            ltype = f" ({it['type']})" if it.get('type') else ""
            teacher = f"👤 <i>{it['teacher']}</i>" if it.get('teacher') else ""
            loc = f"📍 {it['location']}" if it.get('location') else ""
            details = " | ".join(filter(None, [teacher, loc]))

            text.append(f"▫️ <b>{interval}</b> | <b>{subj}</b>{ltype}\n   {details}\n")
        else:
            text.append(f"▫️ <b>{interval}</b>:")
            for it in items:
                sg = f"[{it['subgroup']} подгр.] " if it.get('subgroup') else ""
                subj = it.get('subject', it.get('summary', 'Пара'))
                ltype = f" ({it['type']})" if it.get('type') else ""
                teacher = f"👤 <i>{it['teacher']}</i>" if it.get('teacher') else ""
                loc = f"📍 {it['location']}" if it.get('location') else ""
                details = " | ".join(filter(None, [teacher, loc]))

                text.append(f"   • {sg}<b>{subj}</b>{ltype}\n     {details}")
            text.append("")

    return "\n".join(text).strip()


@dp.message(Command('start', 'help'))
async def cmd_start(message: types.Message):
    kb = None
    if WEBAPP_URL:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📱 Открыть расписание (Mini App)", web_app=WebAppInfo(url=WEBAPP_URL))],
                [InlineKeyboardButton(text="📅 Скачать календарь", url=f"{WEBAPP_URL}/calendar.ics")]
            ]
        )

    await message.answer(
        "👋 Привет! Я бот с расписанием занятий ВятГУ.\n\n"
        "Вы можете открыть современный <b>Mini App</b> прямо в Telegram или использовать команды:\n"
        "▫️ /today — Пары на сегодня\n"
        "▫️ /tomorrow — Пары на завтра\n"
        "▫️ /week — Расписание на текущую неделю\n"
        "▫️ /calendar — Подписка на календарь в iPhone / Android\n",
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )


@dp.message(Command('today'))
async def cmd_today(message: types.Message):
    today = datetime.datetime.now(TIMEZONE).date()
    text = format_day_schedule(today)
    await message.answer(text, parse_mode=ParseMode.HTML)


@dp.message(Command('tomorrow'))
async def cmd_tomorrow(message: types.Message):
    tomorrow = datetime.datetime.now(TIMEZONE).date() + datetime.timedelta(days=1)
    text = format_day_schedule(tomorrow)
    await message.answer(text, parse_mode=ParseMode.HTML)


@dp.message(Command('week'))
async def cmd_week(message: types.Message):
    today = datetime.datetime.now(TIMEZONE).date()
    start_of_week = today - datetime.timedelta(days=today.weekday())

    blocks = []
    for day_offset in range(6):  # Пн-Сб
        day_date = start_of_week + datetime.timedelta(days=day_offset)
        blocks.append(format_day_schedule(day_date))

    separator = "\n\n" + "—" * 20 + "\n\n"
    response = separator.join(blocks)

    if len(response) > 4000:
        for chunk in [response[i:i + 3800] for i in range(0, len(response), 3800)]:
            await message.answer(chunk, parse_mode=ParseMode.HTML)
    else:
        await message.answer(response, parse_mode=ParseMode.HTML)


@dp.message(Command('calendar'))
async def cmd_calendar(message: types.Message):
    base_cal_url = f"{WEBAPP_URL}/calendar.ics" if WEBAPP_URL else ICS_URL
    webcal_all = base_cal_url.replace('https://', 'webcal://').replace('http://', 'webcal://')
    webcal_sg1 = f"{webcal_all}?subgroup=1"
    webcal_sg2 = f"{webcal_all}?subgroup=2"

    https_sg1 = f"{base_cal_url}?subgroup=1"
    https_sg2 = f"{base_cal_url}?subgroup=2"

    kb_buttons = []
    if WEBAPP_URL:
        kb_buttons.append([InlineKeyboardButton(text="📱 Открыть в Mini App", web_app=WebAppInfo(url=WEBAPP_URL))])
    kb_buttons.append([InlineKeyboardButton(text="📥 Скачать .ics (1 подгруппа)", url=https_sg1)])
    kb_buttons.append([InlineKeyboardButton(text="📥 Скачать .ics (2 подгруппа)", url=https_sg2)])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)

    await message.answer(
        "📲 <b>Подписка на календарь:</b>\n\n"
        "Расписание синхронизируется на телефоне само, с виджетами и напоминаниями!\n\n"
        "🍏 <b>iPhone / iPad / Mac (Apple Calendar):</b>\n"
        "Скопируйте ссылку и вставьте в адресную строку Safari:\n"
        f"• 1 подгруппа: <code>{webcal_sg1}</code>\n"
        f"• 2 подгруппа: <code>{webcal_sg2}</code>\n"
        f"• Все пары: <code>{webcal_all}</code>\n\n"
        "🤖 <b>Android / Google Календарь:</b>\n"
        "1. Откройте <a href=\"https://calendar.google.com/\">Google Календарь</a> с компьютера.\n"
        "2. В блоке «Другие календари» нажмите <b>«+»</b> ➔ <b>«Добавить по URL»</b>.\n"
        f"3. Вставьте ссылку: <code>{https_sg1}</code>\n\n"
        "<i>Или нажмите кнопку ниже, чтобы скачать файл и открыть на телефоне.</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
        disable_web_page_preview=True
    )


# WebApp & API эндпоинты
async def handle_index(request):
    """Отдает главную страницу Mini App."""
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            return web.Response(text=f.read(), content_type='text/html')
    return web.Response(text="Шаблон Mini App не найден.", status=404)


async def handle_api_schedule(request):
    """JSON API для Mini App (мгновенный ответ из памяти)."""
    lessons = get_cached_lessons()
    return web.json_response({
        'lessons': lessons,
        'count': len(lessons),
        'server_url': WEBAPP_URL
    })


async def handle_calendar_ics(request):
    """Генерирует и отдает .ics файл с поддержкой фильтрации по подгруппе."""
    subgroup_param = request.query.get('subgroup', '')
    lessons = get_cached_lessons()

    if subgroup_param in ('1', '2'):
        sg = int(subgroup_param)
        lessons = [l for l in lessons if not l.get('subgroup') or l.get('subgroup') == sg]

    cal = Calendar()
    cal.creator = 'Vyatsu Schedule Bot'

    for item in lessons:
        event = Event()
        event.uid = item['uid']
        event.name = item.get('summary', item.get('subject', 'Пара'))
        event.location = item.get('location', '')

        desc_parts = []
        if item.get('type'):
            desc_parts.append(f"Тип: {item['type']}")
        if item.get('teacher'):
            desc_parts.append(f"Преподаватель: {item['teacher']}")
        if item.get('subgroup'):
            desc_parts.append(f"Подгруппа: {item['subgroup']}")
        if item.get('location'):
            desc_parts.append(f"Место: {item['location']}")

        event.description = '\n'.join(desc_parts) if desc_parts else item.get('description', '')
        event.begin = datetime.datetime.fromisoformat(item['start'])
        event.end = datetime.datetime.fromisoformat(item['end'])
        cal.events.add(event)

    cal_title = f"ВятГУ ПМИб-1301 ({subgroup_param} подгр.)" if subgroup_param in ('1', '2') else "Расписание ВятГУ ПМИб-1301"
    ics_text = cal.serialize()
    custom_headers = (
        f"X-WR-CALNAME:{cal_title}\r\n"
        "X-WR-TIMEZONE:Europe/Kirov\r\n"
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H\r\n"
        "X-PUBLISHED-TTL:PT6H\r\n"
    )
    if "BEGIN:VCALENDAR\r\n" in ics_text:
        ics_text = ics_text.replace("BEGIN:VCALENDAR\r\n", f"BEGIN:VCALENDAR\r\n{custom_headers}")
    else:
        ics_text = ics_text.replace("BEGIN:VCALENDAR\n", f"BEGIN:VCALENDAR\n{custom_headers}")

    return web.Response(
        text=ics_text,
        content_type='text/calendar; charset=utf-8',
        headers={
            'Content-Disposition': 'inline; filename="vyatsu.ics"',
            'Access-Control-Allow-Origin': '*'
        }
    )


async def handle_ping(request):
    """Health check для хостинга (Render)."""
    return web.Response(text="Bot & Mini App are running!")


async def start_webserver():
    port = int(os.getenv('PORT', 8080))
    app = web.Application()
    app.router.add_get('/', handle_index)
    app.router.add_get('/app', handle_index)
    app.router.add_get('/api/schedule', handle_api_schedule)
    app.router.add_get('/calendar.ics', handle_calendar_ics)
    app.router.add_get('/vyatsu.ics', handle_calendar_ics)
    app.router.add_get('/healthz', handle_ping)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Веб-сервер Mini App запущен на порту {port}")


async def main():
    if not BOT_TOKEN:
        logging.error("Не указан BOT_TOKEN в переменных окружения!")
        return

    get_cached_lessons()
    await start_webserver()
    bot = Bot(token=BOT_TOKEN)
    asyncio.create_task(background_cache_worker())

    if WEBAPP_URL:
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Расписание",
                    web_app=WebAppInfo(url=WEBAPP_URL)
                )
            )
            logging.info(f"Кнопка меню WebApp настроена на {WEBAPP_URL}")
        except Exception as e:
            logging.warning(f"Не удалось настроить кнопку WebApp: {e}")

    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
