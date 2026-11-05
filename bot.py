from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
import time
from zoneinfo import ZoneInfo

import aiohttp
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.filters import Command, or_f
from aiogram.types import (
    BotCommand,
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    MenuButtonCommands,
    ReplyKeyboardMarkup,
)
from aiohttp import web
from ics import Calendar, Event

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

BOT_TOKEN = os.getenv('BOT_TOKEN', '')
TIMEZONE = ZoneInfo('Europe/Kirov')
CACHE_FILE = 'lessons_cache.json'
USER_SETTINGS_FILE = 'user_settings.json'

DATA_URL = os.getenv('DATA_URL', '')
WEBAPP_URL = os.getenv('WEBAPP_URL', '').rstrip('/')
CDN_BASE_URL = "https://cdn.jsdelivr.net/gh/RTX0ffer/vyatsu-schedule@main"
CALENDARS_DIR = "calendars"
ICS_URL = f"{CDN_BASE_URL}/{CALENDARS_DIR}/pmib/vyatsu_1301.ics"

FACULTIES = {
    'fkfmn': {
        'name': 'Факультет компьютерных и физико-математических наук',
        'short': 'ФКФМН',
        'badge': '📐',
        'default_dir': 'pmib',
    },
    'favt': {
        'name': 'Факультет автоматики и вычислительной техники',
        'short': 'ФАВТ',
        'badge': '⚙️',
        'default_dir': 'ivtb',
    },
    'etf': {
        'name': 'Электротехнический факультет',
        'short': 'ЭТФ',
        'badge': '⚡️',
        'default_dir': 'eieb',
    },
    'fsa': {
        'name': 'Факультет строительства и архитектуры',
        'short': 'ФСА',
        'badge': '🏗',
        'default_dir': 'stb',
    },
    'ftid': {
        'name': 'Факультет технологий, инжиниринга и дизайна',
        'short': 'ФТИД',
        'badge': '🎨',
        'default_dir': 'msb',
    },
    'inhe': {
        'name': 'Институт химии и экологии',
        'short': 'ИнХимЭк',
        'badge': '🧪',
        'default_dir': 'htb',
    },
    'inbio': {
        'name': 'Институт биологии и биотехнологии',
        'short': 'ИнБиоБиз',
        'badge': '🌿',
        'default_dir': 'bb',
    },
    'ui': {
        'name': 'Юридический институт',
        'short': 'ЮИ',
        'badge': '⚖️',
        'default_dir': 'yurb',
    },
    'fef': {
        'name': 'Факультет экономики и финансов',
        'short': 'ФЭФ',
        'badge': '💰',
        'default_dir': 'eknb',
    },
    'fms': {
        'name': 'Факультет менеджмента и сервиса',
        'short': 'ФМС',
        'badge': '💼',
        'default_dir': 'mnb',
    },
    'fipnik': {
        'name': 'Факультет истории, полит. наук и культурологии',
        'short': 'ФИПНиК',
        'badge': '🏛',
        'default_dir': 'isb',
    },
    'fl': {
        'name': 'Факультет лингвистики',
        'short': 'ФЛ',
        'badge': '🗣',
        'default_dir': 'lvb',
    },
    'fmo': {
        'name': 'Факультет международного образования',
        'short': 'ФМО',
        'badge': '🌍',
        'default_dir': 'lvb_mo',
    },
    'fryalim': {
        'name': 'Факультет русского языка, литературы и медиакоммуникаций',
        'short': 'ФРЯЛиМ',
        'badge': '📚',
        'default_dir': 'rsob',
    },
    'fpip': {
        'name': 'Факультет педагогики и психологии',
        'short': 'ФПиП',
        'badge': '🧠',
        'default_dir': 'plb',
    },
    'ped': {
        'name': 'Дирекция ОП Педагогического института',
        'short': 'Пединститут',
        'badge': '🎓',
        'default_dir': 'podb',
    },
    'ffkis': {
        'name': 'Факультет физической культуры и спорта',
        'short': 'ФФКиС',
        'badge': '🏃‍♂️',
        'default_dir': 'fkb',
    },
}

DEFAULT_DIRECTIONS = {
    # 📐 ФКФМН
    'pmib': {'name': 'Прикладная математика и информатика', 'short': 'ПМИб', 'code_spec': '01.03.02', 'badge': '📐', 'faculty': 'fkfmn'},
    'mkb': {'name': 'Математика и компьютерные науки', 'short': 'МКб', 'code_spec': '02.03.01', 'badge': '🔢', 'faculty': 'fkfmn'},
    'fib': {'name': 'Фундаментальная информатика и ИТ', 'short': 'ФИб', 'code_spec': '02.03.02', 'badge': '💻', 'faculty': 'fkfmn'},

    # ⚙️ ФАВТ
    'ivtb': {'name': 'Информатика и вычислительная техника', 'short': 'ИВТб', 'code_spec': '09.03.01', 'badge': '🖥', 'faculty': 'favt'},
    'inbb': {'name': 'Информационная безопасность', 'short': 'ИНБб', 'code_spec': '10.03.01', 'badge': '🔐', 'faculty': 'favt'},
    'iktb': {'name': 'Инфокоммуникационные технологии и системы связи', 'short': 'ИКТб', 'code_spec': '11.03.02', 'badge': '📡', 'faculty': 'favt'},
    'utb': {'name': 'Управление в технических системах', 'short': 'УТб', 'code_spec': '27.03.04', 'badge': '⚙️', 'faculty': 'favt'},
    'inbs': {'name': 'Информационная безопасность телеком. систем (Специалитет)', 'short': 'ИНБс', 'code_spec': '10.05.02', 'badge': '🛡', 'faculty': 'favt'},

    # ⚡️ ЭТФ
    'eieb': {'name': 'Электроэнергетика и электротехника', 'short': 'ЭиЭб', 'code_spec': '13.03.02', 'badge': '⚡️', 'faculty': 'etf'},
    'mrb': {'name': 'Мехатроника и робототехника', 'short': 'МРб', 'code_spec': '15.03.06', 'badge': '🤖', 'faculty': 'etf'},
    'titb': {'name': 'Теплоэнергетика и теплотехника', 'short': 'ТиТб', 'code_spec': '13.03.01', 'badge': '🔥', 'faculty': 'etf'},

    # 🏗 ФСА
    'stb': {'name': 'Строительство', 'short': 'СТб', 'code_spec': '08.03.01', 'badge': '🏗', 'faculty': 'fsa'},
    'tbb': {'name': 'Техносферная безопасность', 'short': 'ТБб', 'code_spec': '20.03.01', 'badge': '🦺', 'faculty': 'fsa'},
    'gsb': {'name': 'Городское строительство и хозяйство', 'short': 'ГСб', 'code_spec': '08.03.01', 'badge': '🏙', 'faculty': 'fsa'},

    # 🎨 ФТИД
    'msb': {'name': 'Машиностроение', 'short': 'МСб', 'code_spec': '15.03.01', 'badge': '🏭', 'faculty': 'ftid'},
    'thob': {'name': 'Технология художественной обработки материалов', 'short': 'ТХОб', 'code_spec': '29.03.04', 'badge': '🏺', 'faculty': 'ftid'},
    'mtb': {'name': 'Материаловедение и технологии материалов', 'short': 'МТб', 'code_spec': '22.03.01', 'badge': '🔬', 'faculty': 'ftid'},
    'mlb': {'name': 'Металлургия', 'short': 'МЛб', 'code_spec': '22.03.02', 'badge': '⚒', 'faculty': 'ftid'},
    'db': {'name': 'Дизайн', 'short': 'Дб', 'code_spec': '54.03.01', 'badge': '🎨', 'faculty': 'ftid'},
    'ptks': {'name': 'Проектирование технологических машин (Специалитет)', 'short': 'ПТКс', 'code_spec': '15.05.01', 'badge': '⚙️', 'faculty': 'ftid'},

    # 🧪 ИнХимЭк
    'htb': {'name': 'Химическая технология', 'short': 'ХТб', 'code_spec': '18.03.01', 'badge': '🧪', 'faculty': 'inhe'},
    'hmb': {'name': 'Химия', 'short': 'ХМб', 'code_spec': '04.03.01', 'badge': '⚗️', 'faculty': 'inhe'},
    'ggb': {'name': 'География', 'short': 'ГГб', 'code_spec': '05.03.02', 'badge': '🌍', 'faculty': 'inhe'},
    'ldb': {'name': 'Ландшафтная архитектура', 'short': 'ЛДб', 'code_spec': '35.03.10', 'badge': '🌳', 'faculty': 'inhe'},

    # 🌿 ИнБиоБиз
    'bb': {'name': 'Биология', 'short': 'Бб', 'code_spec': '06.03.01', 'badge': '🧬', 'faculty': 'inbio'},
    'btb': {'name': 'Биотехнология', 'short': 'БТб', 'code_spec': '19.03.01', 'badge': '🧫', 'faculty': 'inbio'},

    # ⚖️ ЮИ
    'yurb': {'name': 'Юриспруденция', 'short': 'ЮРб', 'code_spec': '40.03.01', 'badge': '⚖️', 'faculty': 'ui'},
    'pnbs': {'name': 'Правовое обеспечение нац. безопасности (Специалитет)', 'short': 'ПНБс', 'code_spec': '40.05.01', 'badge': '🛡', 'faculty': 'ui'},
    'tads': {'name': 'Таможенное дело (Специалитет)', 'short': 'ТАДс', 'code_spec': '38.05.02', 'badge': '📦', 'faculty': 'ui'},
    'pds': {'name': 'Правоохранительная деятельность (Специалитет)', 'short': 'ПДс', 'code_spec': '40.05.02', 'badge': '🚔', 'faculty': 'ui'},

    # 💰 ФЭФ
    'eknb': {'name': 'Экономика', 'short': 'ЭКНб', 'code_spec': '38.03.01', 'badge': '📈', 'faculty': 'fef'},
    'bib': {'name': 'Бизнес-информатика', 'short': 'БИб', 'code_spec': '38.03.05', 'badge': '💼', 'faculty': 'fef'},
    'ebs': {'name': 'Экономическая безопасность (Специалитет)', 'short': 'ЭБс', 'code_spec': '38.05.01', 'badge': '💳', 'faculty': 'fef'},

    # 💼 ФМС
    'mnb': {'name': 'Менеджмент', 'short': 'МНб', 'code_spec': '38.03.02', 'badge': '📊', 'faculty': 'fms'},
    'gmb': {'name': 'Государственное и муниципальное управление', 'short': 'ГМб', 'code_spec': '38.03.04', 'badge': '🏛', 'faculty': 'fms'},
    'inb': {'name': 'Инноватика', 'short': 'ИНб', 'code_spec': '27.03.05', 'badge': '💡', 'faculty': 'fms'},
    'trb': {'name': 'Туризм', 'short': 'ТРб', 'code_spec': '43.03.02', 'badge': '✈️', 'faculty': 'fms'},
    'upb': {'name': 'Управление персоналом', 'short': 'УПб', 'code_spec': '38.03.03', 'badge': '👥', 'faculty': 'fms'},

    # 🏛 ФИПНиК
    'isb': {'name': 'История', 'short': 'ИСб', 'code_spec': '46.03.01', 'badge': '📜', 'faculty': 'fipnik'},
    'ormb': {'name': 'Организация работы с молодежью', 'short': 'ОРМб', 'code_spec': '39.03.03', 'badge': '🤝', 'faculty': 'fipnik'},
    'scb': {'name': 'Социология', 'short': 'СЦб', 'code_spec': '39.03.01', 'badge': '👥', 'faculty': 'fipnik'},

    # 🗣 ФЛ
    'lvb': {'name': 'Лингвистика', 'short': 'ЛВб', 'code_spec': '45.03.02', 'badge': '🗣', 'faculty': 'fl'},

    # 🌍 ФМО
    'lvb_mo': {'name': 'Лингвистика (Международное образование)', 'short': 'ЛВб', 'code_spec': '45.03.02', 'badge': '🌍', 'faculty': 'fmo'},

    # 📚 ФРЯЛиМ
    'rsob': {'name': 'Реклама и связи с общественностью', 'short': 'РСОб', 'code_spec': '42.03.01', 'badge': '📢', 'faculty': 'fryalim'},
    'zhkb': {'name': 'Журналистика', 'short': 'ЖКб', 'code_spec': '42.03.02', 'badge': '📰', 'faculty': 'fryalim'},
    'flb': {'name': 'Филология', 'short': 'ФЛб', 'code_spec': '45.03.01', 'badge': '📖', 'faculty': 'fryalim'},

    # 🧠 ФПиП
    'plb': {'name': 'Психология', 'short': 'ПЛб', 'code_spec': '37.03.01', 'badge': '🧠', 'faculty': 'fpip'},
    'sdob': {'name': 'Специальное (дефектологическое) образование', 'short': 'СДОб', 'code_spec': '44.03.03', 'badge': '🧸', 'faculty': 'fpip'},

    # 🎓 Пединститут
    'podb': {'name': 'Педагогическое образование', 'short': 'ПОДб', 'code_spec': '44.03.05', 'badge': '👩‍🏫', 'faculty': 'ped'},

    # 🏃‍♂️ ФФКиС
    'fkb': {'name': 'Физическая культура', 'short': 'ФКб', 'code_spec': '49.03.01', 'badge': '⚽️', 'faculty': 'ffkis'},
    'afkb': {'name': 'Адаптивная физическая культура', 'short': 'АФКб', 'code_spec': '49.03.02', 'badge': '🏃‍♂️', 'faculty': 'ffkis'},
}

DEFAULT_SUPPORTED_GROUPS = {
    # =========================================================================
    # 🏛 Факультет компьютерных и физико-математических наук (ФКФМН)
    # =========================================================================

    # 01.03.02 Прикладная математика и информатика (ПМИб)
    '27021': {'name': 'ПМИб-1301', 'course': 1, 'direction': 'pmib', 'full_name': 'ПМИб-1301-52-00', 'code': '1301'},
    '27022': {'name': 'ПМИб-1302', 'course': 1, 'direction': 'pmib', 'full_name': 'ПМИб-1302-52-00', 'code': '1302'},
    '26498': {'name': 'ПМИб-2301', 'course': 2, 'direction': 'pmib', 'full_name': 'ПМИб-2301-52-00', 'code': '2301'},
    '26256': {'name': 'ПМИб-3301', 'course': 3, 'direction': 'pmib', 'full_name': 'ПМИб-3301-52-00', 'code': '3301'},
    '26418': {'name': 'ПМИб-4301', 'course': 4, 'direction': 'pmib', 'full_name': 'ПМИб-4301-52-00', 'code': '4301'},

    # 02.03.01 Математика и компьютерные науки (МКб)
    '27023': {'name': 'МКб-1301', 'course': 1, 'direction': 'mkb', 'full_name': 'МКб-1301-51-00', 'code': 'mkb_1301'},
    '26547': {'name': 'МКб-2301', 'course': 2, 'direction': 'mkb', 'full_name': 'МКб-2301-51-00', 'code': 'mkb_2301'},
    '26574': {'name': 'МКб-3301', 'course': 3, 'direction': 'mkb', 'full_name': 'МКб-3301-51-00', 'code': 'mkb_3301'},
    '26495': {'name': 'МКб-4301', 'course': 4, 'direction': 'mkb', 'full_name': 'МКб-4301-51-00', 'code': 'mkb_4301'},

    # 02.03.02 Фундаментальная информатика и ИТ (ФИб)
    '27024': {'name': 'ФИб-1301', 'course': 1, 'direction': 'fib', 'full_name': 'ФИб-1301-51-00', 'code': 'fib_1301'},
    '27025': {'name': 'ФИб-1302', 'course': 1, 'direction': 'fib', 'full_name': 'ФИб-1302-51-00', 'code': 'fib_1302'},
    '26570': {'name': 'ФИб-2301', 'course': 2, 'direction': 'fib', 'full_name': 'ФИб-2301-51-00', 'code': 'fib_2301'},
    '26923': {'name': 'ФИб-2302', 'course': 2, 'direction': 'fib', 'full_name': 'ФИб-2302-51-00', 'code': 'fib_2302'},
    '26248': {'name': 'ФИб-3301', 'course': 3, 'direction': 'fib', 'full_name': 'ФИб-3301-51-00', 'code': 'fib_3301'},
    '26892': {'name': 'ФИб-4301', 'course': 4, 'direction': 'fib', 'full_name': 'ФИб-4301-51-00', 'code': 'fib_4301'},
    '26589': {'name': 'ФИб-4302', 'course': 4, 'direction': 'fib', 'full_name': 'ФИб-4302-51-00', 'code': 'fib_4302'},

    # =========================================================================
    # ⚙️ Факультет автоматики и вычислительной техники (ФАВТ)
    # =========================================================================

    # 09.03.01 Информатика и вычислительная техника (ИВТб)
    '27032': {'name': 'ИВТб-1301', 'course': 1, 'direction': 'ivtb', 'full_name': 'ИВТб-1301-06-00', 'code': 'ivtb_1301'},
    '27033': {'name': 'ИВТб-1302', 'course': 1, 'direction': 'ivtb', 'full_name': 'ИВТб-1302-06-00', 'code': 'ivtb_1302'},
    '27034': {'name': 'ИВТб-1303', 'course': 1, 'direction': 'ivtb', 'full_name': 'ИВТб-1303-06-00', 'code': 'ivtb_1303'},
    '27035': {'name': 'ИВТб-1304', 'course': 1, 'direction': 'ivtb', 'full_name': 'ИВТб-1304-06-00', 'code': 'ivtb_1304'},
    '27036': {'name': 'ИВТб-1305', 'course': 1, 'direction': 'ivtb', 'full_name': 'ИВТб-1305-06-00', 'code': 'ivtb_1305'},
    '27037': {'name': 'ИВТб-1306', 'course': 1, 'direction': 'ivtb', 'full_name': 'ИВТб-1306-06-00', 'code': 'ivtb_1306'},
    '26342': {'name': 'ИВТб-2301', 'course': 2, 'direction': 'ivtb', 'full_name': 'ИВТб-2301-06-00', 'code': 'ivtb_2301'},
    '26690': {'name': 'ИВТб-2302', 'course': 2, 'direction': 'ivtb', 'full_name': 'ИВТб-2302-06-00', 'code': 'ivtb_2302'},
    '26514': {'name': 'ИВТб-2303', 'course': 2, 'direction': 'ivtb', 'full_name': 'ИВТб-2303-06-00', 'code': 'ivtb_2303'},
    '26885': {'name': 'ИВТб-2304', 'course': 2, 'direction': 'ivtb', 'full_name': 'ИВТб-2304-06-00', 'code': 'ivtb_2304'},
    '26504': {'name': 'ИВТб-2305', 'course': 2, 'direction': 'ivtb', 'full_name': 'ИВТб-2305-06-00', 'code': 'ivtb_2305'},
    '26319': {'name': 'ИВТб-2306', 'course': 2, 'direction': 'ivtb', 'full_name': 'ИВТб-2306-06-00', 'code': 'ivtb_2306'},
    '26833': {'name': 'ИВТб-3301', 'course': 3, 'direction': 'ivtb', 'full_name': 'ИВТб-3301-05-00', 'code': 'ivtb_3301'},
    '26774': {'name': 'ИВТб-3302', 'course': 3, 'direction': 'ivtb', 'full_name': 'ИВТб-3302-05-00', 'code': 'ivtb_3302'},
    '26222': {'name': 'ИВТб-3303', 'course': 3, 'direction': 'ivtb', 'full_name': 'ИВТб-3303-05-00', 'code': 'ivtb_3303'},
    '26661': {'name': 'ИВТб-3304', 'course': 3, 'direction': 'ivtb', 'full_name': 'ИВТб-3304-05-00', 'code': 'ivtb_3304'},
    '26392': {'name': 'ИВТб-4301', 'course': 4, 'direction': 'ivtb', 'full_name': 'ИВТб-4301-05-00', 'code': 'ivtb_4301'},
    '26759': {'name': 'ИВТб-4302', 'course': 4, 'direction': 'ivtb', 'full_name': 'ИВТб-4302-05-00', 'code': 'ivtb_4302'},
    '26254': {'name': 'ИВТб-4303', 'course': 4, 'direction': 'ivtb', 'full_name': 'ИВТб-4303-05-00', 'code': 'ivtb_4303'},

    # 10.03.01 Информационная безопасность (ИНБб)
    '27038': {'name': 'ИНБб-1301', 'course': 1, 'direction': 'inbb', 'full_name': 'ИНБб-1301-02-00', 'code': 'inbb_1301'},
    '27039': {'name': 'ИНБб-1302', 'course': 1, 'direction': 'inbb', 'full_name': 'ИНБб-1302-02-00', 'code': 'inbb_1302'},
    '26365': {'name': 'ИНБб-2301', 'course': 2, 'direction': 'inbb', 'full_name': 'ИНБб-2301-02-00', 'code': 'inbb_2301'},
    '26686': {'name': 'ИНБб-2302', 'course': 2, 'direction': 'inbb', 'full_name': 'ИНБб-2302-02-00', 'code': 'inbb_2302'},
    '26861': {'name': 'ИНБб-3301', 'course': 3, 'direction': 'inbb', 'full_name': 'ИНБб-3301-02-00', 'code': 'inbb_3301'},
    '26497': {'name': 'ИНБб-3302', 'course': 3, 'direction': 'inbb', 'full_name': 'ИНБб-3302-02-00', 'code': 'inbb_3302'},
    '26769': {'name': 'ИНБб-4301', 'course': 4, 'direction': 'inbb', 'full_name': 'ИНБб-4301-02-00', 'code': 'inbb_4301'},

    # 11.03.02 Инфокоммуникационные технологии и системы связи (ИКТб)
    '27040': {'name': 'ИКТб-1301', 'course': 1, 'direction': 'iktb', 'full_name': 'ИКТб-1301-05-00', 'code': 'iktb_1301'},
    '27041': {'name': 'ИКТб-1302', 'course': 1, 'direction': 'iktb', 'full_name': 'ИКТб-1302-05-00', 'code': 'iktb_1302'},
    '26407': {'name': 'ИКТб-2301', 'course': 2, 'direction': 'iktb', 'full_name': 'ИКТб-2301-05-00', 'code': 'iktb_2301'},
    '26353': {'name': 'ИКТб-2302', 'course': 2, 'direction': 'iktb', 'full_name': 'ИКТб-2302-05-00', 'code': 'iktb_2302'},
    '26265': {'name': 'ИКТб-3301', 'course': 3, 'direction': 'iktb', 'full_name': 'ИКТб-3301-04-00', 'code': 'iktb_3301'},
    '26758': {'name': 'ИКТб-4301', 'course': 4, 'direction': 'iktb', 'full_name': 'ИКТб-4301-04-00', 'code': 'iktb_4301'},

    # 27.03.04 Управление в технических системах (УТб)
    '27051': {'name': 'УТб-1301', 'course': 1, 'direction': 'utb', 'full_name': 'УТб-1301-02-00', 'code': 'utb_1301'},
    '26586': {'name': 'УТб-2301', 'course': 2, 'direction': 'utb', 'full_name': 'УТб-2301-02-00', 'code': 'utb_2301'},
    '26665': {'name': 'УТб-3301', 'course': 3, 'direction': 'utb', 'full_name': 'УТб-3301-02-00', 'code': 'utb_3301'},
    '26277': {'name': 'УТб-4301', 'course': 4, 'direction': 'utb', 'full_name': 'УТб-4301-02-00', 'code': 'utb_4301'},

    # 10.05.02 Информационная безопасность телекоммуникационных систем (ИНБс, Специалитет)
    '27127': {'name': 'ИНБс-1301', 'course': 1, 'direction': 'inbs', 'full_name': 'ИНБс-1301-01-00', 'code': 'inbs_1301'},
    '26476': {'name': 'ИНБс-2301', 'course': 2, 'direction': 'inbs', 'full_name': 'ИНБс-2301-01-00', 'code': 'inbs_2301'},
    '26326': {'name': 'ИНБс-2302', 'course': 2, 'direction': 'inbs', 'full_name': 'ИНБс-2302-01-00', 'code': 'inbs_2302'},
    '26459': {'name': 'ИНБс-3301', 'course': 3, 'direction': 'inbs', 'full_name': 'ИНБс-3301-01-00', 'code': 'inbs_3301'},
    '26370': {'name': 'ИНБс-4301', 'course': 4, 'direction': 'inbs', 'full_name': 'ИНБс-4301-01-00', 'code': 'inbs_4301'},
    '26640': {'name': 'ИНБс-5301', 'course': 5, 'direction': 'inbs', 'full_name': 'ИНБс-5301-01-00', 'code': 'inbs_5301'},
}

GROUPS_FILE = 'groups.json'
GROUPS_URL = os.getenv('GROUPS_URL') or (DATA_URL.replace('lessons_cache.json', 'groups.json') if 'lessons_cache.json' in DATA_URL else '')
DIRECTIONS_FILE = 'directions.json'
DIRECTIONS_URL = os.getenv('DIRECTIONS_URL') or (DATA_URL.replace('lessons_cache.json', 'directions.json') if 'lessons_cache.json' in DATA_URL else '')


class DynamicDirections(dict):
    """Словарь направлений с авто-перезагрузкой из directions.json при изменении файла."""

    def __init__(self, fallback: dict):
        super().__init__(fallback)
        self.directions_file = DIRECTIONS_FILE
        self._fallback = dict(fallback)
        self._last_mtime = 0
        self._check_reload()

    def _check_reload(self):
        if os.path.exists(self.directions_file):
            try:
                mtime = os.path.getmtime(self.directions_file)
                if mtime != self._last_mtime:
                    with open(self.directions_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if data and isinstance(data, dict):
                        self.clear()
                        self.update(self._fallback)
                        self.update(data)
                        self._last_mtime = mtime
            except Exception as e:
                logging.warning(f"Ошибка перезагрузки {self.directions_file}: {e}")

    def __getitem__(self, key):
        self._check_reload()
        return super().__getitem__(key)

    def get(self, key, default=None):
        self._check_reload()
        return super().get(key, default)

    def items(self):
        self._check_reload()
        return super().items()

    def values(self):
        self._check_reload()
        return super().values()

    def keys(self):
        self._check_reload()
        return super().keys()

    def __contains__(self, key):
        self._check_reload()
        return super().__contains__(key)

    def __iter__(self):
        self._check_reload()
        return super().__iter__()

    def __len__(self):
        self._check_reload()
        return super().__len__()


DIRECTIONS = DynamicDirections(DEFAULT_DIRECTIONS)


class DynamicGroups(dict):
    """Словарь поддерживаемых групп с авто-перезагрузкой из groups.json при изменении файла."""

    def __init__(self, fallback: dict):
        super().__init__(fallback)
        self.groups_file = GROUPS_FILE
        self._last_mtime = 0
        self._check_reload()

    def _check_reload(self):
        if os.path.exists(self.groups_file):
            try:
                mtime = os.path.getmtime(self.groups_file)
                if mtime != self._last_mtime:
                    with open(self.groups_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if data and isinstance(data, dict):
                        self.clear()
                        self.update(data)
                        self._last_mtime = mtime
            except Exception as e:
                logging.warning(f"Ошибка перезагрузки {self.groups_file}: {e}")

    def __getitem__(self, key):
        self._check_reload()
        return super().__getitem__(key)

    def get(self, key, default=None):
        self._check_reload()
        return super().get(key, default)

    def items(self):
        self._check_reload()
        return super().items()

    def values(self):
        self._check_reload()
        return super().values()

    def keys(self):
        self._check_reload()
        return super().keys()

    def __contains__(self, key):
        self._check_reload()
        return super().__contains__(key)

    def __iter__(self):
        self._check_reload()
        return super().__iter__()

    def __len__(self):
        self._check_reload()
        return super().__len__()


SUPPORTED_GROUPS = DynamicGroups(DEFAULT_SUPPORTED_GROUPS)


def get_default_group_id() -> str:
    """Динамически находит ID группы по умолчанию (предпочтительно 1 курс ПМИб)."""
    for gid, ginfo in SUPPORTED_GROUPS.items():
        if ginfo.get('direction') == 'pmib' and ginfo.get('course') == 1:
            return gid
    if SUPPORTED_GROUPS:
        return next(iter(SUPPORTED_GROUPS))
    return '27021'


DEFAULT_GROUP_ID = get_default_group_id()


def get_user_group(user_id: int | str) -> str:
    """Возвращает ID выбранной пользователем группы (с валидацией актуальности группы)."""
    def_id = get_default_group_id()
    if os.path.exists(USER_SETTINGS_FILE):
        try:
            with open(USER_SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                saved_id = settings.get(str(user_id))
                if saved_id and saved_id in SUPPORTED_GROUPS:
                    return saved_id
        except Exception:
            pass
    return def_id


def set_user_group(user_id: int | str, group_id: str):
    """Сохраняет выбранную пользователем группу."""
    settings = {}
    if os.path.exists(USER_SETTINGS_FILE):
        try:
            with open(USER_SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        except Exception:
            settings = {}
    settings[str(user_id)] = group_id
    tmp = f"{USER_SETTINGS_FILE}.tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
    os.replace(tmp, USER_SETTINGS_FILE)


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
                raw_lessons = list(data.get('lessons', {}).values())
                # Фильтруем только актуальные уроки
                lessons = [l for l in raw_lessons if 'direction' in l or l.get('group_id') in SUPPORTED_GROUPS]
                # Дедупликация занятий (по группе, времени, предмету и подгруппе)
                unique_lessons = []
                seen = set()
                for l in lessons:
                    key = (l.get('group_id'), l['start'], l['end'], l.get('subject', l.get('summary')), l.get('subgroup'))
                    if key not in seen:
                        seen.add(key)
                        unique_lessons.append(l)

                if unique_lessons:
                    _memory_cache['lessons'] = unique_lessons
                    _memory_cache['timestamp'] = time.time()
                    logging.info(f'Мгновенно загружено {len(unique_lessons)} уникальных пар из локального файла.')
                    return unique_lessons
        except Exception as e:
            logging.error(f'Ошибка чтения локального файла: {e}')

    return []


async def sync_remote_cache():
    """Фоновая асинхронная проверка обновлений с GitHub."""
    # 1. Фоновая синхронизация списка групп (Auto-Discovery с GitHub)
    if GROUPS_URL:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(GROUPS_URL, timeout=8) as resp:
                    if resp.status == 200:
                        remote_groups = await resp.json(content_type=None)
                        if remote_groups and isinstance(remote_groups, dict) and remote_groups != dict(SUPPORTED_GROUPS):
                            tmp = f"{GROUPS_FILE}.tmp"
                            with open(tmp, 'w', encoding='utf-8') as f:
                                json.dump(remote_groups, f, ensure_ascii=False, indent=2)
                            os.replace(tmp, GROUPS_FILE)
                            SUPPORTED_GROUPS.clear()
                            SUPPORTED_GROUPS.update(remote_groups)
                            logging.info(f"Фоновое обновление: синхронизировано {len(remote_groups)} групп с GitHub.")
        except Exception as e:
            logging.warning(f"Фоновое обновление групп с GitHub не удалось: {e}")

    # 1b. Фоновая синхронизация списка направлений с GitHub
    if DIRECTIONS_URL:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(DIRECTIONS_URL, timeout=8) as resp:
                    if resp.status == 200:
                        remote_dirs = await resp.json(content_type=None)
                        if remote_dirs and isinstance(remote_dirs, dict) and remote_dirs != dict(DIRECTIONS):
                            tmp = f"{DIRECTIONS_FILE}.tmp"
                            with open(tmp, 'w', encoding='utf-8') as f:
                                json.dump(remote_dirs, f, ensure_ascii=False, indent=2)
                            os.replace(tmp, DIRECTIONS_FILE)
                            DIRECTIONS.clear()
                            DIRECTIONS.update(DEFAULT_DIRECTIONS)
                            DIRECTIONS.update(remote_dirs)
                            logging.info(f"Фоновое обновление: синхронизировано {len(remote_dirs)} направлений с GitHub.")
        except Exception as e:
            logging.warning(f"Фоновое обновление направлений с GitHub не удалось: {e}")

    # 2. Фоновая синхронизация расписания
    if not DATA_URL:
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(DATA_URL, timeout=8) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    raw_lessons = list(data.get('lessons', {}).values())
                    lessons = [l for l in raw_lessons if 'direction' in l or l.get('group_id') in SUPPORTED_GROUPS]
                    unique_lessons = []
                    seen = set()
                    for l in lessons:
                        key = (l.get('group_id'), l['start'], l['end'], l.get('subject', l.get('summary')), l.get('subgroup'))
                        if key not in seen:
                            seen.add(key)
                            unique_lessons.append(l)

                    if unique_lessons:
                        _memory_cache['lessons'] = unique_lessons
                        _memory_cache['timestamp'] = time.time()
                        logging.info(f'Фоновое обновление: загружено {len(unique_lessons)} уникальных пар с GitHub.')
    except Exception as e:
        logging.warning(f'Фоновое обновление с GitHub не удалось: {e}')


async def background_cache_worker():
    """Периодически раз в 20 минут в фоне обновляет кэш."""
    while True:
        await asyncio.sleep(1200)
        await sync_remote_cache()


async def keep_alive_worker():
    """Каждые 8 минут отправляет HTTP-запрос на собственный URL, чтобы бесплатный сервер Render не уходил в спящий режим."""
    server_url = os.getenv('RENDER_EXTERNAL_URL') or os.getenv('WEBAPP_URL', '').rstrip('/')
    if not server_url:
        return
    health_url = f"{server_url}/healthz"
    logging.info(f"Keep-alive воркер запущен: пинг каждые 8 минут -> {health_url}")
    # Небольшая пауза перед первым пингом, чтобы веб-сервер успел запуститься
    await asyncio.sleep(60)
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(health_url, timeout=10) as resp:
                    if resp.status == 200:
                        logging.info("Keep-alive пинг успешен: сервер бодрствует.")
                    else:
                        logging.warning(f"Keep-alive пинг вернул статус {resp.status}")
        except Exception as e:
            logging.warning(f"Keep-alive пинг не удался: {e}")
        await asyncio.sleep(480)  # 8 минут (Render засыпает через 15 минут)


def format_day_schedule(target_date: datetime.date, group_id: str = DEFAULT_GROUP_ID):
    """Форматирует расписание на день в безопасном формате HTML для выбранной группы."""
    all_lessons = get_cached_lessons()
    lessons = [
        l for l in all_lessons
        if l.get('group_id') == group_id
    ]
    # Дедупликация на уровне дня
    unique_lessons = []
    seen = set()
    for item in lessons:
        key = (item['start'], item['end'], item.get('subject', item.get('summary')), item.get('subgroup'))
        if key not in seen:
            seen.add(key)
            unique_lessons.append(item)
    lessons = unique_lessons
    ginfo = SUPPORTED_GROUPS.get(group_id, SUPPORTED_GROUPS[DEFAULT_GROUP_ID])
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
            return f"📅 <b>{weekday_name}, {date_str}</b> | <b>{ginfo['name']}</b>\n\n🎉 <b>Праздничный день: {holiday_name}!</b>\nПар нет, отличного отдыха!"
        if target_date.weekday() == 5:
            return f"📅 <b>{weekday_name}, {date_str}</b> | <b>{ginfo['name']}</b>\n\n🎉 В субботу пар нет! Выходной."
        if target_date.weekday() == 6:
            return f"📅 <b>{weekday_name}, {date_str}</b> | <b>{ginfo['name']}</b>\n\n🎉 Воскресенье — выходной день!"
        return f"📅 <b>{weekday_name}, {date_str}</b> | <b>{ginfo['name']}</b>\n\n🎉 В этот день пар нет! Можно отдыхать."

    by_time = {}
    for start_dt, item in day_lessons:
        end_dt = datetime.datetime.fromisoformat(item['end']).astimezone(TIMEZONE)
        interval = f"{start_dt.strftime('%H:%M')} – {end_dt.strftime('%H:%M')}"
        by_time.setdefault(interval, []).append(item)

    text = [f"📅 <b>{weekday_name}, {date_str}</b> | <b>{ginfo['name']} ({ginfo['course']} курс)</b>\n"]
    for interval, items in by_time.items():
        if len(items) == 1:
            it = items[0]
            sg = f"[{it['subgroup']} подгр.] " if it.get('subgroup') else ""
            subj = it.get('subject', it.get('summary', 'Пара'))
            ltype = f" ({it['type']})" if it.get('type') else ""
            teacher = f"👤 <i>{it['teacher']}</i>" if it.get('teacher') else ""
            loc = f"📍 {it['location']}" if it.get('location') else ""
            details = " | ".join(filter(None, [teacher, loc]))

            text.append(f"▫️ <b>{interval}</b> | {sg}<b>{subj}</b>{ltype}\n   {details}\n")
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


def get_main_keyboard():
    """Создает постоянную клавиатуру с кнопками под полем ввода."""
    buttons = [
        [
            KeyboardButton(text="📅 Сегодня"),
            KeyboardButton(text="📆 Завтра")
        ],
        [
            KeyboardButton(text="🗓 На неделю"),
            KeyboardButton(text="📲 Календарь")
        ],
        [
            KeyboardButton(text="👥 Курс / Группа")
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Выберите действие в меню..."
    )


def get_faculty_selection_keyboard(active_fac: str = 'fkfmn') -> InlineKeyboardMarkup:
    """Генерирует аккуратную сетку выбора всех 17 факультетов/институтов ВятГУ."""
    rows = []
    fac_items = list(FACULTIES.items())
    for i in range(0, len(fac_items), 2):
        chunk = fac_items[i:i + 2]
        row = []
        for f_key, f_val in chunk:
            is_active = (f_key == active_fac)
            label = f"• {f_val['badge']} {f_val['short']} •" if is_active else f"{f_val['badge']} {f_val['short']}"
            row.append(InlineKeyboardButton(text=label, callback_data=f"fac_{f_key}"))
        rows.append(row)

    rows.append([
        InlineKeyboardButton(text="⬅️ Назад к группам", callback_data="back_to_groups")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_faculty_selection_text(user_id: int | str) -> str:
    """Формирует текст меню выбора факультета."""
    gid = get_user_group(user_id)
    ginfo = SUPPORTED_GROUPS.get(gid, SUPPORTED_GROUPS.get(get_default_group_id(), {}))
    return (
        "🏛 <b>Выберите факультет или институт ВятГУ:</b>\n\n"
        f"Ваша текущая группа: <b>{ginfo.get('name', 'Не выбрана')}</b>\n\n"
        "👇 <i>Нажмите на нужный факультет, чтобы открыть его направления и группы:</i>"
    )


def get_group_selection_keyboard(active_dir: str = 'pmib') -> InlineKeyboardMarkup:
    """Генерирует инлайн-клавиатуру: кнопка смены факультета, вкладки направлений и группы по курсам."""
    active_fac = DIRECTIONS.get(active_dir, {}).get('faculty', 'fkfmn')
    fac_info = FACULTIES.get(active_fac, FACULTIES['fkfmn'])

    inline_keyboard = [
        # Верхняя кнопка: смена факультета
        [InlineKeyboardButton(
            text=f"🏛 Факультет: {fac_info['badge']} {fac_info['short']} ▾",
            callback_data="open_fac_list"
        )]
    ]

    # Строки направлений активного факультета, отсортированные по ступеням обучения:
    # Бакалавриат -> Специалитет -> Магистратура -> Аспирантура
    degree_order = {'bachelor': 0, 'specialist': 1, 'master': 2, 'phd': 3}
    dir_keys = [k for k, v in DIRECTIONS.items() if v.get('faculty') == active_fac]
    dir_keys.sort(key=lambda k: (degree_order.get(DIRECTIONS[k].get('degree', 'bachelor'), 9), k))

    dir_rows = []
    current_row = []
    for d_key in dir_keys:
        d_val = DIRECTIONS[d_key]
        is_active = (d_key == active_dir)
        badge = d_val.get('badge', '')
        short = d_val['short']
        label = f"• {badge} {short} •" if is_active else f"{badge} {short}"
        current_row.append(InlineKeyboardButton(text=label, callback_data=f"dir_{d_key}"))
        if len(current_row) == 3:
            dir_rows.append(current_row)
            current_row = []
    if current_row:
        dir_rows.append(current_row)

    inline_keyboard.extend(dir_rows)

    # Группы активного направления, сгруппированные по курсу
    dir_groups = [
        (gid, ginfo) for gid, ginfo in SUPPORTED_GROUPS.items()
        if ginfo.get('direction') == active_dir
    ]

    by_course: dict[int, list[tuple[str, dict]]] = {}
    for gid, ginfo in dir_groups:
        by_course.setdefault(ginfo['course'], []).append((gid, ginfo))

    active_dinfo = DIRECTIONS.get(active_dir, {})
    deg_badge = active_dinfo.get('badge', '🎓')

    for course in sorted(by_course.keys()):
        c_groups = by_course[course]
        if len(c_groups) == 1:
            gid, ginfo = c_groups[0]
            inline_keyboard.append([
                InlineKeyboardButton(text=f"{deg_badge} {course} курс: {ginfo['name']}", callback_data=f"set_grp_{gid}")
            ])
        elif len(c_groups) == 2:
            row = [
                InlineKeyboardButton(text=f"{deg_badge} {course} к.: {ginfo['name']}", callback_data=f"set_grp_{gid}")
                for gid, ginfo in c_groups
            ]
            inline_keyboard.append(row)
        else:
            # Для 3+ групп разбиваем по 2 кнопки в ряд для компактности
            for i in range(0, len(c_groups), 2):
                chunk = c_groups[i:i + 2]
                row = [
                    InlineKeyboardButton(text=f"{deg_badge} {course} к.: {ginfo['name']}", callback_data=f"set_grp_{gid}")
                    for gid, ginfo in chunk
                ]
                inline_keyboard.append(row)

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def get_group_selection_text(user_id: int | str, active_dir: str = 'pmib') -> str:
    """Формирует текст сообщения выбора группы для указанного направления."""
    gid = get_user_group(user_id)
    ginfo = SUPPORTED_GROUPS.get(gid, SUPPORTED_GROUPS.get(DEFAULT_GROUP_ID, {}))
    dinfo = DIRECTIONS.get(active_dir, DIRECTIONS.get('pmib', {}))
    fac_key = dinfo.get('faculty', 'fkfmn')
    fac_info = FACULTIES.get(fac_key, FACULTIES.get('fkfmn', {}))

    deg_names = {
        'bachelor': '🎓 Бакалавриат',
        'specialist': '🔒 Специалитет',
        'master': '🎓 Магистратура',
        'phd': '🔬 Аспирантура'
    }
    deg_str = deg_names.get(dinfo.get('degree'), '🎓 Высшее образование')
    spec_code = dinfo.get('code_spec', '')
    spec_name = dinfo.get('name', '')
    short_code = dinfo.get('short', '')

    spec_line = f"📖 <b>{spec_code} {spec_name}</b> ({short_code})\n" if spec_code else f"📖 <b>{spec_name}</b>\n"

    return (
        f"👥 <b>Выбор факультета, направления и группы</b>\n\n"
        f"🏛 <b>{fac_info.get('name', '')}</b>\n"
        f"📚 Ступень: <b>{deg_str}</b>\n"
        f"{spec_line}\n"
        f"Текущая выбранная группа: <b>{ginfo.get('name', 'Не выбрана')}</b>\n\n"
        f"<i>Нажмите на нужную группу ниже для мгновенного переключения:</i>"
    )

    return (
        f"👥 <b>Выбор факультета, направления и группы</b>\n\n"
        f"🏛 <b>{fac_info['name']}</b>\n"
        f"Вкладка: <b>{dinfo['badge']} {dinfo['name']} ({dinfo['short']})</b>\n"
        f"Специальность: <code>{dinfo['code_spec']}</code>\n"
        f"Ваша активная группа: <b>{ginfo['name']} ({ginfo['course']} курс)</b>\n\n"
        f"👇 <i>Выберите группу ниже или нажмите «🏛 Факультет», чтобы сменить его:</i>"
    )


@dp.message(or_f(Command('group', 'course'), F.text.casefold().in_({'👥 курс / группа', 'курс / группа', 'выбрать группу', 'сменить группу', 'курс'})))
async def cmd_choose_group(message: types.Message):
    gid = get_user_group(message.from_user.id)
    ginfo = SUPPORTED_GROUPS.get(gid, SUPPORTED_GROUPS[DEFAULT_GROUP_ID])
    active_dir = ginfo.get('direction', 'pmib')
    text = get_group_selection_text(message.from_user.id, active_dir=active_dir)
    kb = get_group_selection_keyboard(active_dir=active_dir)
    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@dp.callback_query(lambda c: c.data == 'open_fac_list')
async def callback_open_fac_list(callback: types.CallbackQuery):
    await callback.answer()
    gid = get_user_group(callback.from_user.id)
    ginfo = SUPPORTED_GROUPS.get(gid, SUPPORTED_GROUPS.get(get_default_group_id(), {}))
    active_dir = ginfo.get('direction', 'pmib')
    active_fac = DIRECTIONS.get(active_dir, {}).get('faculty', 'fkfmn')
    kb = get_faculty_selection_keyboard(active_fac=active_fac)
    text = get_faculty_selection_text(callback.from_user.id)
    try:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    except Exception:
        pass


@dp.callback_query(lambda c: c.data == 'back_to_groups')
async def callback_back_to_groups(callback: types.CallbackQuery):
    await callback.answer()
    gid = get_user_group(callback.from_user.id)
    ginfo = SUPPORTED_GROUPS.get(gid, SUPPORTED_GROUPS.get(get_default_group_id(), {}))
    active_dir = ginfo.get('direction', 'pmib')
    text = get_group_selection_text(callback.from_user.id, active_dir=active_dir)
    kb = get_group_selection_keyboard(active_dir=active_dir)
    try:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    except Exception:
        pass


@dp.callback_query(lambda c: c.data and c.data.startswith('fac_'))
async def callback_switch_faculty(callback: types.CallbackQuery):
    await callback.answer()
    fac_key = callback.data.replace('fac_', '')
    if fac_key not in FACULTIES:
        fac_key = 'favt'
    active_dir = FACULTIES[fac_key]['default_dir']
    text = get_group_selection_text(callback.from_user.id, active_dir=active_dir)
    kb = get_group_selection_keyboard(active_dir=active_dir)
    try:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    except Exception:
        pass


@dp.callback_query(lambda c: c.data and c.data.startswith('dir_'))
async def callback_switch_direction(callback: types.CallbackQuery):
    await callback.answer()
    active_dir = callback.data.replace('dir_', '')
    if active_dir not in DIRECTIONS:
        active_dir = 'pmib'
    text = get_group_selection_text(callback.from_user.id, active_dir=active_dir)
    kb = get_group_selection_keyboard(active_dir=active_dir)
    try:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    except Exception:
        pass


@dp.callback_query(lambda c: c.data and c.data.startswith('set_grp_'))
async def callback_select_group(callback: types.CallbackQuery):
    await callback.answer()
    gid = callback.data.replace('set_grp_', '')
    if gid in SUPPORTED_GROUPS:
        set_user_group(callback.from_user.id, gid)
        ginfo = SUPPORTED_GROUPS[gid]
        dinfo = DIRECTIONS.get(ginfo.get('direction', 'pmib'), {})
        dir_title = f"{dinfo.get('badge', '')} {dinfo.get('name', '')} ({dinfo.get('short', '')})" if dinfo else ""
        await callback.message.answer(
            f"✅ <b>Группа переключена на {ginfo['name']} ({ginfo['course']} курс)!</b>\n"
            f"Направление: <b>{dir_title}</b>\n\n"
            f"Теперь команды <b>📅 Сегодня</b>, <b>📆 Завтра</b>, <b>🗓 На неделю</b> и <b>📲 Календарь</b> настроены для вашей группы.\n\n"
            f"<i>Вы всегда можете изменить направление и группу через кнопку «👥 Курс / Группа» или команду /group.</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_keyboard()
        )


@dp.message(or_f(Command('start', 'help'), F.text.casefold().in_({'меню', 'start', 'помощь', 'главное меню'})))
async def cmd_start(message: types.Message):
    gid = get_user_group(message.from_user.id)
    ginfo = SUPPORTED_GROUPS.get(gid, SUPPORTED_GROUPS[DEFAULT_GROUP_ID])
    dinfo = DIRECTIONS.get(ginfo.get('direction', 'pmib'), {})
    dir_title = f"{dinfo.get('badge', '')} {dinfo.get('name', '')} ({dinfo.get('short', '')})" if dinfo else ""

    inline_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📲 Календарь и подписка (.ics)", callback_data="open_calendar_cmd")],
            [InlineKeyboardButton(text="👥 Сменить группу / курс", callback_data="change_grp_from_cal")]
        ]
    )

    await message.answer(
        "👋 Привет! Я бот с расписанием занятий ВятГУ.\n\n"
        f"Направление: <b>{dir_title}</b>\n"
        f"Ваша активная группа: <b>{ginfo['name']} ({ginfo['course']} курс)</b>\n\n"
        "Нажимайте на удобные кнопки внизу экрана или используйте команды:\n"
        "▫️ <b>📅 Сегодня</b> — Пары на сегодня\n"
        "▫️ <b>📆 Завтра</b> — Пары на завтра\n"
        "▫️ <b>🗓 На неделю</b> — Расписание на текущую неделю\n"
        "▫️ <b>📲 Календарь</b> — Подписка и перенос пар в смартфон\n"
        "▫️ <b>👥 Курс / Группа</b> — Выбор направления и курса (ПМИб, МКб, ФИб, 1–4 курсы)\n",
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_keyboard()
    )


@dp.message(or_f(Command('today'), F.text.casefold().in_({'📅 сегодня', 'сегодня'})))
async def cmd_today(message: types.Message):
    gid = get_user_group(message.from_user.id)
    today = datetime.datetime.now(TIMEZONE).date()
    text = format_day_schedule(today, group_id=gid)
    inline_kb = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="📆 На завтра", callback_data="quick_tomorrow")
        ]]
    )
    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=inline_kb)


@dp.message(or_f(Command('tomorrow'), F.text.casefold().in_({'📆 завтра', 'завтра'})))
async def cmd_tomorrow(message: types.Message):
    gid = get_user_group(message.from_user.id)
    tomorrow = datetime.datetime.now(TIMEZONE).date() + datetime.timedelta(days=1)
    text = format_day_schedule(tomorrow, group_id=gid)
    inline_kb = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="📅 На сегодня", callback_data="quick_today")
        ]]
    )
    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=inline_kb)


@dp.message(or_f(Command('week'), F.text.casefold().in_({'🗓 на неделю', 'на неделю', 'неделя'})))
async def cmd_week(message: types.Message):
    gid = get_user_group(message.from_user.id)
    today = datetime.datetime.now(TIMEZONE).date()
    start_of_week = today - datetime.timedelta(days=today.weekday())

    blocks = []
    for day_offset in range(6):  # Пн-Сб
        day_date = start_of_week + datetime.timedelta(days=day_offset)
        blocks.append(format_day_schedule(day_date, group_id=gid))

    separator = "\n\n" + "—" * 20 + "\n\n"
    response = separator.join(blocks)

    if len(response) > 4000:
        for chunk in [response[i:i + 3800] for i in range(0, len(response), 3800)]:
            await message.answer(chunk, parse_mode=ParseMode.HTML)
    else:
        await message.answer(response, parse_mode=ParseMode.HTML)


def build_ics_content(group_id=DEFAULT_GROUP_ID, subgroup=None):
    """Генерирует RFC 5545-совместимый .ics контент со всеми обязательными полями (DTSTAMP, STATUS)."""
    all_lessons = get_cached_lessons()
    lessons = [
        l for l in all_lessons
        if l.get('group_id') == group_id or (not l.get('group_id') and group_id == DEFAULT_GROUP_ID)
    ]
    if subgroup in (1, 2, '1', '2'):
        sg = int(subgroup)
        lessons = [l for l in lessons if not l.get('subgroup') or l.get('subgroup') == sg]

    # Дедупликация занятий
    unique_lessons = []
    seen = set()
    for item in lessons:
        key = (item['start'], item['end'], item.get('subject', item.get('summary')), item.get('subgroup'))
        if key not in seen:
            seen.add(key)
            unique_lessons.append(item)
    lessons = unique_lessons

    ginfo = SUPPORTED_GROUPS.get(group_id, SUPPORTED_GROUPS[DEFAULT_GROUP_ID])
    cal = Calendar()
    cal.creator = '-//Vyatsu//Schedule Bot//RU'
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

    cal_title = f"ВятГУ {ginfo['name']} ({subgroup} подгр.)" if subgroup in (1, 2, '1', '2') else f"Расписание ВятГУ {ginfo['name']}"
    ics_text = cal.serialize()
    custom_headers = (
        "CALSCALE:GREGORIAN\r\n"
        "METHOD:PUBLISH\r\n"
        f"X-WR-CALNAME:{cal_title}\r\n"
        "X-WR-TIMEZONE:Europe/Kirov\r\n"
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H\r\n"
        "X-PUBLISHED-TTL:PT6H\r\n"
    )
    prodid_str = "PRODID:-//Vyatsu//Schedule Bot//RU\r\n"
    if prodid_str in ics_text:
        ics_text = ics_text.replace(prodid_str, f"{prodid_str}{custom_headers}")
    elif "VERSION:2.0\r\n" in ics_text:
        ics_text = ics_text.replace("VERSION:2.0\r\n", f"VERSION:2.0\r\n{custom_headers}")
    else:
        ics_text = ics_text.replace("BEGIN:VCALENDAR\r\n", f"BEGIN:VCALENDAR\r\n{custom_headers}")

    return ics_text


async def send_calendar_message(message: types.Message, user_id: int | str = None):
    uid = user_id or (message.from_user.id if message.from_user else None)
    gid = get_user_group(uid) if uid else DEFAULT_GROUP_ID
    ginfo = SUPPORTED_GROUPS.get(gid, SUPPORTED_GROUPS[DEFAULT_GROUP_ID])
    dinfo = DIRECTIONS.get(ginfo.get('direction', 'pmib'), {})
    code = ginfo.get('code', '1301')
    fac_key = dinfo.get('faculty', 'fkfmn')
    fac_info = FACULTIES.get(fac_key, FACULTIES['fkfmn'])
    dir_title = f"{dinfo.get('badge', '')} {dinfo.get('name', '')} ({dinfo.get('short', '')})" if dinfo else ""

    direction = ginfo.get('direction', 'pmib')
    cdn_sg1 = f"{CDN_BASE_URL}/{CALENDARS_DIR}/{direction}/vyatsu_{code}_sg1.ics"
    cdn_sg2 = f"{CDN_BASE_URL}/{CALENDARS_DIR}/{direction}/vyatsu_{code}_sg2.ics"
    cdn_all = f"{CDN_BASE_URL}/{CALENDARS_DIR}/{direction}/vyatsu_{code}.ics"

    webcal_sg1 = cdn_sg1.replace('https://', 'webcal://')
    webcal_sg2 = cdn_sg2.replace('https://', 'webcal://')
    webcal_all = cdn_all.replace('https://', 'webcal://')

    kb_buttons = [
        [
            InlineKeyboardButton(text=f"📱 {ginfo['name']} (1 подгр.)", callback_data=f"send_ics_{gid}_1"),
            InlineKeyboardButton(text=f"📱 {ginfo['name']} (2 подгр.)", callback_data=f"send_ics_{gid}_2")
        ],
        [
            InlineKeyboardButton(text=f"📱 {ginfo['name']} (Все пары)", callback_data=f"send_ics_{gid}_all")
        ],
        [
            InlineKeyboardButton(text="👥 Сменить группу / курс", callback_data="change_grp_from_cal")
        ]
    ]

    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)

    await message.answer(
        f"📲 <b>Календарь расписания ВятГУ:</b>\n"
        f"Факультет: <b>{fac_info['name']}</b>\n"
        f"Направление: <b>{dir_title}</b>\n"
        f"Группа: <b>{ginfo['name']} ({ginfo['course']} курс)</b>\n\n"
        "⚡ <b>Для любого Android (Samsung, Xiaomi, Huawei, Pixel и др.) — В 1 клик:</b>\n"
        "Нажмите кнопку с нужной подгруппой ниже ➔ откройте файл прямо в Telegram ➔ выберите <b>«Календарь»</b> ➔ <b>«Сохранить»</b>.\n"
        "Все пары мгновенно появятся в системном календаре и виджетах с аудиториями и напоминаниями!\n\n"
        "🤖 <b>Google Календарь / 📧 Microsoft Outlook (веб-подписка):</b>\n"
        "1. В Google Календаре нажмите <b>«+»</b> рядом с «Другие календари» ➔ <b>«Добавить по URL»</b>.\n"
        "2. В Microsoft Outlook Web нажмите <b>«Добавить календарь»</b> ➔ <b>«Подписаться из Интернета»</b>.\n"
        "3. Вставьте прямую ссылку (быстрый CDN со 100% поддержкой календарей):\n"
        f"• 1 подгруппа: <code>{cdn_sg1}</code>\n"
        f"• 2 подгруппа: <code>{cdn_sg2}</code>\n"
        f"• Все пары: <code>{cdn_all}</code>\n\n"
        "🍏 <b>iPhone / Mac (Apple Calendar):</b>\n"
        "Скопируйте ссылку и откройте в браузере Safari:\n"
        f"• 1 подгруппа: <code>{webcal_sg1}</code>\n"
        f"• 2 подгруппа: <code>{webcal_sg2}</code>\n\n"
        "<i>💡 Хотите расписание для другого направления или курса? Нажмите «👥 Сменить группу / курс» ниже.</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
        disable_web_page_preview=True
    )


@dp.message(or_f(Command('calendar'), F.text.casefold().in_({'📲 календарь', 'календарь'})))
async def cmd_calendar(message: types.Message):
    await send_calendar_message(message)


@dp.callback_query(lambda c: c.data == 'open_calendar_cmd')
async def callback_open_calendar_cmd(callback: types.CallbackQuery):
    await callback.answer()
    await send_calendar_message(callback.message, user_id=callback.from_user.id)


@dp.callback_query(lambda c: c.data == 'change_grp_from_cal')
async def callback_change_grp_from_cal(callback: types.CallbackQuery):
    await callback.answer()
    gid = get_user_group(callback.from_user.id)
    ginfo = SUPPORTED_GROUPS.get(gid, SUPPORTED_GROUPS[DEFAULT_GROUP_ID])
    active_dir = ginfo.get('direction', 'pmib')
    text = get_group_selection_text(callback.from_user.id, active_dir=active_dir)
    kb = get_group_selection_keyboard(active_dir=active_dir)
    await callback.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@dp.callback_query(lambda c: c.data == 'quick_today')
async def callback_quick_today(callback: types.CallbackQuery):
    await callback.answer()
    gid = get_user_group(callback.from_user.id)
    today = datetime.datetime.now(TIMEZONE).date()
    text = format_day_schedule(today, group_id=gid)
    inline_kb = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="📆 На завтра", callback_data="quick_tomorrow")
        ]]
    )
    await callback.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=inline_kb)


@dp.callback_query(lambda c: c.data == 'quick_tomorrow')
async def callback_quick_tomorrow(callback: types.CallbackQuery):
    await callback.answer()
    gid = get_user_group(callback.from_user.id)
    tomorrow = datetime.datetime.now(TIMEZONE).date() + datetime.timedelta(days=1)
    text = format_day_schedule(tomorrow, group_id=gid)
    inline_kb = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="📅 На сегодня", callback_data="quick_today")
        ]]
    )
    await callback.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=inline_kb)


@dp.callback_query(lambda c: c.data and c.data.startswith('send_ics_'))
async def callback_send_ics_file(callback: types.CallbackQuery):
    await callback.answer()
    parts = callback.data.split('_')[2:]  # после send_ics_
    if len(parts) == 1:
        gid = get_user_group(callback.from_user.id)
        mode = parts[0]
    else:
        gid = parts[0]
        mode = parts[1]

    sg = 1 if mode == '1' else 2 if mode == '2' else None
    ginfo = SUPPORTED_GROUPS.get(gid, SUPPORTED_GROUPS[DEFAULT_GROUP_ID])
    sg_label = f" ({sg} подгруппа)" if sg else " (Все пары)"
    filename = f"vyatsu_{ginfo['code']}_sg{sg}.ics" if sg else f"vyatsu_{ginfo['code']}.ics"

    ics_content = build_ics_content(group_id=gid, subgroup=sg).encode('utf-8')
    file = BufferedInputFile(ics_content, filename=filename)

    await callback.message.answer_document(
        document=file,
        caption=(
            f"📅 <b>Файл расписания {ginfo['name']}{sg_label}</b>\n\n"
            "📱 <b>Инструкция для смартфона (Samsung, Xiaomi, Huawei, Pixel, iPhone):</b>\n"
            "1. Нажмите на этот файл прямо здесь в Telegram.\n"
            "2. Выберите системное приложение <b>«Календарь»</b> вашего смартфона.\n"
            "3. Нажмите <b>«Сохранить»</b> (или «Импортировать»).\n\n"
            "✨ Все пары мгновенно появятся в виджетах и календаре телефона с аудиториями, корпусами и напоминаниями за 15 минут!\n"
            "<i>💡 Это разовый импорт пар в память телефона. Для автоматического обновления расписания каждую ночь используйте веб-подписку по ссылке из сообщения выше (Google / Outlook / Safari).</i>"
        ),
        parse_mode=ParseMode.HTML
    )


async def handle_calendar_ics_subgroup(request, subgroup, group_id=DEFAULT_GROUP_ID):
    """Отдает чистый .ics файл без query-параметров для конкретной подгруппы."""
    ics_text = build_ics_content(group_id=group_id, subgroup=subgroup)
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


async def handle_calendar_dynamic_ics(request):
    """Динамический эндпоинт для отдачи календаря любой группы и подгруппы."""
    target = request.match_info.get('target', '')
    sg = None
    if target.endswith('_sg1') or target.endswith('_subgroup1'):
        sg = 1
        code = target.replace('_sg1', '').replace('_subgroup1', '')
    elif target.endswith('_sg2') or target.endswith('_subgroup2'):
        sg = 2
        code = target.replace('_sg2', '').replace('_subgroup2', '')
    else:
        code = target

    gid = DEFAULT_GROUP_ID
    for g_id, g_info in SUPPORTED_GROUPS.items():
        if g_id == code or g_info['code'] == code:
            gid = g_id
            break

    ics_text = build_ics_content(group_id=gid, subgroup=sg)
    return web.Response(
        text=ics_text,
        content_type='text/calendar',
        charset='utf-8',
        headers={
            'Content-Disposition': f'inline; filename="vyatsu_{target}.ics"',
            'Access-Control-Allow-Origin': '*',
            'Cache-Control': 'no-cache, no-store, must-revalidate'
        }
    )


async def handle_calendar_ics(request):
    """Генерирует и отдает .ics файл со всеми обязательными RFC-полями (DTSTAMP, STATUS)."""
    subgroup_param = request.query.get('subgroup', '')
    sg = int(subgroup_param) if subgroup_param in ('1', '2') else None
    gid = request.query.get('group', DEFAULT_GROUP_ID)
    if gid not in SUPPORTED_GROUPS:
        gid = DEFAULT_GROUP_ID
    return web.Response(
        text=build_ics_content(group_id=gid, subgroup=sg),
        content_type='text/calendar',
        charset='utf-8',
        headers={
            'Content-Disposition': 'inline; filename="vyatsu.ics"',
            'Access-Control-Allow-Origin': '*',
            'Cache-Control': 'no-cache, no-store, must-revalidate'
        }
    )


async def handle_ping(request):
    """Health check для хостинга (Render)."""
    return web.Response(text="Vyatsu Schedule Bot is running!")


async def start_webserver():
    port = int(os.getenv('PORT', 8080))
    app = web.Application()
    app.router.add_get('/', handle_ping)
    app.router.add_get('/healthz', handle_ping)
    app.router.add_get('/calendar.ics', handle_calendar_ics)
    app.router.add_get('/vyatsu.ics', handle_calendar_ics)
    app.router.add_get('/calendars/vyatsu.ics', handle_calendar_ics)
    app.router.add_get('/calendar/subgroup1.ics', lambda r: handle_calendar_ics_subgroup(r, 1))
    app.router.add_get('/calendar/subgroup2.ics', lambda r: handle_calendar_ics_subgroup(r, 2))
    app.router.add_get('/calendar/all.ics', lambda r: handle_calendar_ics_subgroup(r, None))
    app.router.add_get('/vyatsu_subgroup1.ics', lambda r: handle_calendar_ics_subgroup(r, 1))
    app.router.add_get('/vyatsu_subgroup2.ics', lambda r: handle_calendar_ics_subgroup(r, 2))
    app.router.add_get('/calendar/{target}.ics', handle_calendar_dynamic_ics)
    app.router.add_get('/vyatsu_{target}.ics', handle_calendar_dynamic_ics)
    app.router.add_get('/calendars/{direction}/vyatsu_{target}.ics', handle_calendar_dynamic_ics)
    app.router.add_get('/calendars/{direction}/{target}.ics', handle_calendar_dynamic_ics)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Веб-сервер календаря и healthz запущен на порту {port}")


async def main():
    if not BOT_TOKEN:
        logging.error("Не указан BOT_TOKEN в переменных окружения!")
        return

    get_cached_lessons()
    await start_webserver()
    bot = Bot(token=BOT_TOKEN)
    asyncio.create_task(background_cache_worker())
    asyncio.create_task(keep_alive_worker())

    # Регистрация списка команд в Telegram (кнопка Меню)
    commands = [
        BotCommand(command="today", description="Пары на сегодня"),
        BotCommand(command="tomorrow", description="Пары на завтра"),
        BotCommand(command="week", description="Расписание на неделю"),
        BotCommand(command="group", description="Выбор курса и группы"),
        BotCommand(command="calendar", description="Календарь и подписка (.ics)"),
        BotCommand(command="start", description="Главное меню")
    ]
    try:
        await bot.set_my_commands(commands)
        logging.info("Официальные команды бота успешно зарегистрированы в Telegram")
    except Exception as e:
        logging.warning(f"Не удалось настроить команды меню: {e}")

    try:
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logging.info("Кнопка меню настроена на стандартные команды бота")
    except Exception as e:
        logging.warning(f"Не удалось настроить кнопку Меню: {e}")

    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
