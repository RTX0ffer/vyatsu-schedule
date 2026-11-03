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
from aiogram.types import (
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    WebAppInfo,
)
from aiohttp import web
from ics import Calendar, Event

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

BOT_TOKEN = os.getenv('BOT_TOKEN', '')
TIMEZONE = ZoneInfo('Europe/Kirov')
CACHE_FILE = 'lessons_cache.json'

DATA_URL = os.getenv('DATA_URL', '')
WEBAPP_URL = os.getenv('WEBAPP_URL', '').rstrip('/')
GITHUB_REPO_RAW = "https://raw.githubusercontent.com/RTX0ffer/vyatsu-schedule/main"
ICS_URL = f"{GITHUB_REPO_RAW}/vyatsu.ics"

WEEKDAYS_RU = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']

RUSSIAN_HOLIDAYS = {
    (1, 1): "Новый год 🎄",
    (1, 2): "Новогодние каникулы ❄️",
    (1, 3): "Новогодние каникулы ❄️",
    (1, 4): "Новогодние каникулы ❄️",
    (1, 5): "Новогодние каникулы ❄️",
    (1, 6): "Новогодние каникулы ❄️",
    (1, 7): "Рождество Христово ✨",
    (1, 8): "Новогодние каникулы ❄️",
    (1, 25): "День российского студенчества (Татьянин день) 🎓",
    (2, 23): "День защитника Отечества 🎖",
    (3, 8): "Международный женский день 🌷",
    (5, 1): "Праздник Весны и Труда 🌸",
    (5, 9): "День Победы ⭐️",
    (6, 12): "День России 🇷🇺",
    (11, 4): "День народного единства 🇷🇺",
}

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
        holiday_name = RUSSIAN_HOLIDAYS.get((target_date.month, target_date.day))
        if holiday_name:
            return f"📅 <b>{weekday_name}, {date_str}</b>\n\n🎉 <b>Праздничный день: {holiday_name}!</b>\nПар нет, отличного отдыха!"
        if target_date.weekday() == 5:
            return f"📅 <b>{weekday_name}, {date_str}</b>\n\n🎉 В субботу пар нет! Выходной."
        if target_date.weekday() == 6:
            return f"📅 <b>{weekday_name}, {date_str}</b>\n\n🎉 Воскресенье — выходной день!"
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


def build_ics_content(subgroup=None):
    """Генерирует RFC 5545-совместимый .ics контент со всеми обязательными полями (DTSTAMP, STATUS)."""
    lessons = get_cached_lessons()
    if subgroup in (1, 2, '1', '2'):
        sg = int(subgroup)
        lessons = [l for l in lessons if not l.get('subgroup') or l.get('subgroup') == sg]

    cal = Calendar()
    cal.creator = 'Vyatsu Schedule Bot'
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    for item in lessons:
        event = Event()
        event.uid = item['uid']
        event.name = item.get('summary', item.get('subject', 'Пара'))
        event.location = item.get('location', '')
        # Обязательные поля стандарта RFC 5545 для Google и Apple календарей
        event.created = now_utc
        event.last_modified = now_utc
        event.status = 'CONFIRMED'

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

    cal_title = f"ВятГУ ПМИб-1301 ({subgroup} подгр.)" if subgroup in (1, 2, '1', '2') else "Расписание ВятГУ ПМИб-1301"
    ics_text = cal.serialize()
    custom_headers = (
        "CALSCALE:GREGORIAN\r\n"
        "METHOD:PUBLISH\r\n"
        f"X-WR-CALNAME:{cal_title}\r\n"
        "X-WR-TIMEZONE:Europe/Kirov\r\n"
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H\r\n"
        "X-PUBLISHED-TTL:PT6H\r\n"
    )
    if "BEGIN:VCALENDAR\r\n" in ics_text:
        ics_text = ics_text.replace("BEGIN:VCALENDAR\r\n", f"BEGIN:VCALENDAR\r\n{custom_headers}")
    else:
        ics_text = ics_text.replace("BEGIN:VCALENDAR\n", f"BEGIN:VCALENDAR\n{custom_headers}")

    return ics_text


@dp.message(Command('calendar'))
async def cmd_calendar(message: types.Message):
    gh_sg1 = f"{GITHUB_REPO_RAW}/vyatsu_subgroup1.ics"
    gh_sg2 = f"{GITHUB_REPO_RAW}/vyatsu_subgroup2.ics"
    gh_all = f"{GITHUB_REPO_RAW}/vyatsu.ics"

    webcal_sg1 = gh_sg1.replace('https://', 'webcal://')
    webcal_sg2 = gh_sg2.replace('https://', 'webcal://')
    webcal_all = gh_all.replace('https://', 'webcal://')

    kb_buttons = []
    if WEBAPP_URL:
        kb_buttons.append([InlineKeyboardButton(text="📱 Открыть в Mini App", web_app=WebAppInfo(url=WEBAPP_URL))])
    kb_buttons.append([
        InlineKeyboardButton(text="📱 Файл для Samsung (1 подгр.)", callback_data="send_ics_1"),
        InlineKeyboardButton(text="📱 Файл для Samsung (2 подгр.)", callback_data="send_ics_2")
    ])
    kb_buttons.append([
        InlineKeyboardButton(text="📱 Файл для Samsung (Все пары)", callback_data="send_ics_all")
    ])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)

    await message.answer(
        "📲 <b>Календарь расписания ВятГУ:</b>\n\n"
        "⚡ <b>Для Samsung Galaxy и Android (В 1 клик):</b>\n"
        "Нажмите кнопку <b>«📱 Файл для Samsung»</b> ниже ➔ откройте файл ➔ выберите <b>«Календарь Samsung»</b> ➔ <b>«Сохранить»</b>.\n"
        "Все пары мгновенно появятся в календаре и виджетах телефона с аудиториями и напоминаниями!\n\n"
        "🤖 <b>Google Календарь (веб-подписка):</b>\n"
        "1. Откройте <a href=\"https://calendar.google.com/\">Google Календарь</a> с компьютера.\n"
        "2. В меню «Другие календари» нажмите <b>«+»</b> ➔ <b>«Добавить по URL»</b>.\n"
        "3. Вставьте прямую ссылку (без параметров, чистый .ics от CDN):\n"
        f"• 1 подгруппа: <code>{gh_sg1}</code>\n"
        f"• 2 подгруппа: <code>{gh_sg2}</code>\n"
        f"• Все пары: <code>{gh_all}</code>\n\n"
        "🍏 <b>iPhone / Mac (Apple Calendar):</b>\n"
        "Скопируйте ссылку и откройте в браузере Safari:\n"
        f"• 1 подгруппа: <code>{webcal_sg1}</code>\n"
        f"• 2 подгруппа: <code>{webcal_sg2}</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
        disable_web_page_preview=True
    )


@dp.callback_query(lambda c: c.data and c.data.startswith('send_ics_'))
async def callback_send_ics_file(callback: types.CallbackQuery):
    await callback.answer()
    mode = callback.data.split('_')[-1]
    sg = 1 if mode == '1' else 2 if mode == '2' else None
    sg_label = f" ({sg} подгруппа)" if sg else " (Все пары)"
    filename = f"vyatsu_subgroup_{sg}.ics" if sg else "vyatsu.ics"

    ics_content = build_ics_content(sg).encode('utf-8')
    file = BufferedInputFile(ics_content, filename=filename)

    await callback.message.answer_document(
        document=file,
        caption=(
            f"📅 <b>Файл расписания{sg_label}</b>\n\n"
            "📱 <b>Инструкция для Samsung Galaxy:</b>\n"
            "1. Нажмите на этот файл прямо здесь в Telegram.\n"
            "2. Выберите приложение <b>«Календарь» (Samsung Calendar)</b>.\n"
            "3. Нажмите <b>«Сохранить»</b>.\n\n"
            "✨ Все пары появятся в виджетах и календаре телефона с аудиториями, корпусами и напоминаниями за 15 минут!"
        ),
        parse_mode=ParseMode.HTML
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


async def handle_calendar_ics_subgroup(request, subgroup):
    """Отдает чистый .ics файл без query-параметров для конкретной подгруппы."""
    ics_text = build_ics_content(subgroup)
    fname = f"vyatsu_subgroup_{subgroup}.ics" if subgroup else "vyatsu.ics"
    return web.Response(
        text=ics_text,
        content_type='text/calendar',
        charset='utf-8',
        headers={
            'Content-Disposition': f'inline; filename="{fname}"',
            'Access-Control-Allow-Origin': '*',
            'Cache-Control': 'no-cache, no-store, must-revalidate'
        }
    )


async def handle_calendar_ics(request):
    """Генерирует и отдает .ics файл со всеми обязательными RFC-полями (DTSTAMP, STATUS)."""
    subgroup_param = request.query.get('subgroup', '')
    sg = int(subgroup_param) if subgroup_param in ('1', '2') else None
    return await handle_calendar_ics_subgroup(request, sg)


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
    app.router.add_get('/calendar/subgroup1.ics', lambda r: handle_calendar_ics_subgroup(r, 1))
    app.router.add_get('/calendar/subgroup2.ics', lambda r: handle_calendar_ics_subgroup(r, 2))
    app.router.add_get('/calendar/all.ics', lambda r: handle_calendar_ics_subgroup(r, None))
    app.router.add_get('/vyatsu_subgroup1.ics', lambda r: handle_calendar_ics_subgroup(r, 1))
    app.router.add_get('/vyatsu_subgroup2.ics', lambda r: handle_calendar_ics_subgroup(r, 2))
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
