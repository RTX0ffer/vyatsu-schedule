import concurrent.futures
import datetime
import hashlib
import io
import json
import logging
import os
import re
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import pdfplumber
import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

SCHEDULE_PAGE_URL = 'https://old.vyatsu.ru/studentu-1/spravochnaya-informatsiya/raspisanie-zanyatiy-dlya-studentov.html'

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

DIRECTIONS = {
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
DIRECTIONS_FILE = 'directions.json'

CYR_TO_LAT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
}


def cyr_to_slug(text):
    """Преобразует кириллическую аббревиатуру в безопасный slug для директорий."""
    s = text.lower()
    res = ''.join(CYR_TO_LAT.get(c, c) for c in s)
    return re.sub(r'[^a-z0-9_]+', '', res)


FAC_MAPPING = [
    ('компьютерных', 'fkfmn'),
    ('автоматики', 'favt'),
    ('электротехнический', 'etf'),
    ('строительства', 'fsa'),
    ('технологий', 'ftid'),
    ('химии', 'inhe'),
    ('биологии', 'inbio'),
    ('юридический', 'ui'),
    ('экономики', 'fef'),
    ('менеджмента', 'fms'),
    ('истории', 'fipnik'),
    ('лингвистики', 'fl'),
    ('международного', 'fmo'),
    ('русского', 'fryalim'),
    ('педагогики', 'fpip'),
    ('пединститута', 'ped'),
    ('физической', 'ffkis'),
]

PREF_AND_FAC = {
    (d['faculty'], d['short']): k for k, d in DIRECTIONS.items()
}
PREF_AND_FAC[('fmo', 'ЛВб')] = 'lvb_mo'
PREF_AND_FAC[('fl', 'ЛВб')] = 'lvb'


def discover_groups_and_directions(soup):
    """
    Автоматически находит все группы и направления всех ступеней обучения
    (Бакалавриат, Специалитет, Магистратура, Аспирантура) на странице расписания ВятГУ.
    Возвращает (discovered_groups, discovered_directions).
    """
    if soup is None:
        return {}, {}

    discovered_groups = {}
    discovered_directions = {}

    for h4 in soup.find_all('h4'):
        h4_txt = h4.text.strip()
        m_code = re.match(r'^([\d\.]+)\s+(.*)', h4_txt)
        code_spec = m_code.group(1) if m_code else ''
        spec_name = m_code.group(2) if m_code else h4_txt

        f = h4.find_previous('div', class_='fak_name')
        f_text = f.text.strip().lower() if f else ''
        fac_key = next((k for kw, k in FAC_MAPPING if kw in f_text), None)
        if not fac_key:
            continue

        hep = h4.find_previous('div', class_='headerEduPrograms')
        deg_raw = hep.text.strip() if hep else 'Бакалавр'
        deg_key = 'bachelor'
        if 'Специалист' in deg_raw:
            deg_key = 'specialist'
        elif 'Магистр' in deg_raw:
            deg_key = 'master'
        elif 'Аспирант' in deg_raw:
            deg_key = 'phd'

        curr = h4
        grps = []
        while True:
            curr = curr.find_next()
            if not curr or (curr.name in ['h4', 'div'] and ('headerEduPrograms' in curr.get('class', []) or 'fak_name' in curr.get('class', []))) or curr.name == 'h4':
                break
            if curr.name == 'div' and 'grpPeriod' in curr.get('class', []):
                txt = curr.text.strip()
                raw_pid = curr.get('data-grp_period_id', '').strip()
                grp_id = raw_pid[:-1] if len(raw_pid) > 5 else raw_pid
                grps.append((txt, grp_id))

        if not grps:
            continue

        m_pref = re.match(r'^([А-Яа-яЁё]+)-(\d{4})', grps[0][0])
        if not m_pref:
            continue
        pref = m_pref.group(1)

        dir_key = PREF_AND_FAC.get((fac_key, pref))
        if not dir_key:
            base_slug = cyr_to_slug(pref)
            if pref == 'Ма' and fac_key == 'inbio':
                dir_key = 'ma_inbio'
            elif pref == 'Ма' and fac_key == 'fms':
                dir_key = 'ma_fms'
            elif pref == 'ФЛм' and fac_key == 'fmo':
                dir_key = 'flm_mo'
            elif pref == 'ЛВб' and fac_key == 'fmo':
                dir_key = 'lvb_mo'
            else:
                dir_key = base_slug

        badge = '🎓' if deg_key == 'master' else ('🔬' if deg_key == 'phd' else ('🔒' if deg_key == 'specialist' else '🔹'))
        existing_dir = DIRECTIONS.get(dir_key)
        if existing_dir and 'badge' in existing_dir:
            badge = existing_dir['badge']

        discovered_directions[dir_key] = {
            'name': spec_name,
            'short': pref,
            'code_spec': code_spec,
            'badge': badge,
            'faculty': fac_key,
            'degree': deg_key
        }

        for txt, grp_id in grps:
            m = re.match(r'^([А-Яа-яЁё]+)-(\d{4})', txt)
            if not m:
                continue
            p, num = m.group(1), m.group(2)
            course_digit = int(num[0])
            code = num if dir_key == 'pmib' else f'{dir_key}_{num}'
            discovered_groups[grp_id] = {
                'name': f'{p}-{num}',
                'course': course_digit,
                'direction': dir_key,
                'faculty': fac_key,
                'full_name': txt,
                'code': code
            }

    return discovered_groups, discovered_directions


def discover_groups(soup):
    """Обертка для обратной совместимости: возвращает только группы."""
    groups, _ = discover_groups_and_directions(soup)
    return groups


def load_directions():
    """Загружает обнаруженные направления из directions.json."""
    if os.path.exists(DIRECTIONS_FILE):
        try:
            with open(DIRECTIONS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data and isinstance(data, dict):
                    return data
        except Exception as e:
            logging.warning(f"Не удалось загрузить {DIRECTIONS_FILE}: {e}")
    return {}


def save_directions(directions_dict):
    """Сохраняет направления в directions.json."""
    tmp = f"{DIRECTIONS_FILE}.tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(directions_dict, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DIRECTIONS_FILE)


def load_groups():
    """Загружает обнаруженные группы из groups.json."""
    if os.path.exists(GROUPS_FILE):
        try:
            with open(GROUPS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data and isinstance(data, dict):
                    return data
        except Exception as e:
            logging.warning(f"Не удалось загрузить {GROUPS_FILE}: {e}")
    return {}


def save_groups(groups_dict):
    """Сохраняет группы в groups.json."""
    tmp = f"{GROUPS_FILE}.tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(groups_dict, f, ensure_ascii=False, indent=2)
    os.replace(tmp, GROUPS_FILE)


def get_default_group_id(groups_dict=None):
    """Возвращает ID группы по умолчанию (предпочтительно 1 курс ПМИб)."""
    grps = groups_dict if groups_dict is not None else SUPPORTED_GROUPS
    for gid, ginfo in grps.items():
        if ginfo.get('direction') == 'pmib' and ginfo.get('course') == 1:
            return gid
    if grps:
        return next(iter(grps))
    return '27021'


SUPPORTED_GROUPS = load_groups() or DEFAULT_SUPPORTED_GROUPS
DEFAULT_GROUP_ID = get_default_group_id(SUPPORTED_GROUPS)
GROUP_ID = DEFAULT_GROUP_ID  # Для обратной совместимости
TIMEZONE = ZoneInfo('Europe/Kirov')
CACHE_FILE = 'lessons_cache.json'
CALENDARS_DIR = 'calendars'
ICS_FILE = os.path.join(CALENDARS_DIR, 'pmib', 'vyatsu_1301.ics')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}


def load_cache():
    """Загружает кэш расписания."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.warning(f'Не удалось прочитать кэш: {e}. Начинаем с чистого листа.')
    return {'processed_urls': {}, 'lessons': {}}


def save_cache(cache):
    """Атомарно сохраняет кэш в JSON."""
    tmp_file = f'{CACHE_FILE}.tmp'
    with open(tmp_file, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    os.replace(tmp_file, CACHE_FILE)


def get_pdf_urls_map(soup):
    """Индексирует все актуальные PDF-файлы на странице расписания за один быстрый проход O(N)."""
    pdf_pattern = re.compile(r'/reports/schedule/Group/(\d+)_\d+_(\d{8})_(\d{8})\.pdf')
    today = datetime.date.today()
    pdf_map = {}
    for a_tag in soup.find_all('a', href=pdf_pattern):
        href = a_tag['href']
        m = pdf_pattern.search(href)
        if m:
            gid, start_str, end_str = m.group(1), m.group(2), m.group(3)
            try:
                start_date = datetime.datetime.strptime(start_str, '%d%m%Y').date()
                end_date = datetime.datetime.strptime(end_str, '%d%m%Y').date()
                if end_date >= today:
                    full_url = urljoin('https://old.vyatsu.ru', href)
                    pdf_map.setdefault(gid, []).append((start_date, full_url))
            except Exception:
                continue

    for gid in pdf_map:
        pdf_map[gid].sort(key=lambda x: x[0])
    return pdf_map


def get_group_pdf_urls(group_id=DEFAULT_GROUP_ID, soup=None):
    """Ищет на сайте ВятГУ актуальные PDF-файлы для конкретной группы."""
    if soup is None:
        logging.info('Запрос страницы расписания...')
        session = requests.Session()
        resp = session.get(SCHEDULE_PAGE_URL, headers=HEADERS, timeout=25)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

    pdf_map = get_pdf_urls_map(soup)
    return pdf_map.get(group_id, [])


def detect_weekday(text):
    """Определяет день недели по тексту из ячейки таблицы ВятГУ."""
    tl = text.lower()
    if 'ч' in tl and 'т' in tl: return 3, 'Четверг'
    if 'с' in tl and 'у' in tl and 'б' in tl: return 5, 'Суббота'
    if 'в' in tl and 'с' in tl and 'к' in tl: return 6, 'Воскресенье'
    if 'п' in tl and 'я' in tl: return 4, 'Пятница'
    if 'п' in tl and 'н' in tl: return 0, 'Понедельник'
    if 'с' in tl and 'р' in tl and 'д' in tl: return 2, 'Среда'
    if 'в' in tl and 'т' in tl: return 1, 'Вторник'
    return None, None


def parse_vyatsu_pdf(pdf_bytes, start_date_hint, group_id=DEFAULT_GROUP_ID):
    """Разбирает байты PDF расписания ВятГУ и достает структурированный список занятий."""
    ginfo = SUPPORTED_GROUPS.get(group_id, {'name': 'ПМИб-1301', 'course': 1, 'code': '1301'})
    time_pattern = re.compile(r'(\d{1,2}:\d{2})\s*[-–—]\s*(\d{1,2}:\d{2})')
    lessons = []

    week_offset = 0
    prev_w_idx = -1
    current_time_str = None
    current_date = start_date_hint

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables() or []
            for table in tables:
                for row in table:
                    day_cell = row[0] if len(row) > 0 and row[0] else ''
                    time_cell = row[1] if len(row) > 1 and row[1] else ''
                    subject_cell = row[2] if len(row) > 2 and row[2] else ''

                    # Начало нового дня: вычисляем точную дату по дню недели,
                    # чтобы пропущенные праздничные дни и субботы никогда не сдвигали даты
                    if day_cell and 'День' not in day_cell:
                        w_idx, w_name = detect_weekday(day_cell)
                        if w_idx is not None:
                            if prev_w_idx != -1 and w_idx <= prev_w_idx:
                                week_offset += 7
                            prev_w_idx = w_idx
                            current_date = start_date_hint + datetime.timedelta(days=week_offset + w_idx)

                    # Время занятия
                    t_match = time_pattern.search(time_cell)
                    if t_match:
                        current_time_str = (t_match.group(1), t_match.group(2))

                    # Если есть занятие
                    if subject_cell and subject_cell.strip() and current_time_str and current_date:
                        full_text = ' '.join(subject_cell.split()).strip()
                        if 'Дисциплина' in full_text or 'Время' in full_text:
                            continue

                        # 1. Извлекаем подгруппу
                        sg_match = re.search(r'(\d+)\s*подгруппа', full_text)
                        subgroup = int(sg_match.group(1)) if sg_match else None

                        # 2. Очищаем от номера группы (любое направление: ПМИб, МКб, ФИб)
                        clean_text = re.sub(r'[А-ЯЁа-яё]+-\d+-\d+-\d+,?\s*', '', full_text)

                        # 3. Извлекаем корпус и аудиторию (поддерживаем подчеркивания типа 14-140_ и 14-140)
                        room_m = re.search(r'\b(\d{1,2})-(\d{2,4}[а-яА-Яa-zA-Z]?)(?:_|\b)', clean_text)
                        if room_m:
                            building, room = room_m.group(1), room_m.group(2)
                            location = f'корп. {building}, ауд. {room}'
                        elif 'спортзал' in clean_text.lower():
                            building, room = '', ''
                            location = 'Спортзал'
                        else:
                            building, room = '', ''
                            location = ''

                        # 4. Извлекаем тип занятия
                        type_m = re.search(r'\b(Лекция|Практическое занятие|Лабораторная работа|Консультация|Зачет|Дифференцированный зачет|Экзамен)\b', clean_text)
                        if type_m:
                            lesson_type = type_m.group(1)
                        elif 'практика' in clean_text.lower():
                            lesson_type = 'Практика'
                        else:
                            lesson_type = ''

                        # 5. Извлекаем ФИО преподавателя
                        teacher_m = re.search(r'([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ]\.\s*[А-ЯЁ]\.|\s+[А-ЯЁ]\.))', clean_text)
                        teacher = teacher_m.group(1) if teacher_m else ''

                        # 6. Извлекаем чистое название предмета без аудиторий, типов и преподавателя
                        subj_text = clean_text
                        if sg_match:
                            subj_text = re.sub(r'^\d+\s*подгруппа,?\s*', '', subj_text)
                        if type_m:
                            subj_text = subj_text.split(type_m.group(1))[0]
                        if teacher:
                            subj_text = subj_text.replace(teacher, '')
                        # Очищаем корпус-аудиторию (в т.ч. 14-140_, 14-136_) из названия
                        subj_text = re.sub(r'\b\d{1,2}-\d{2,4}[а-яА-Яa-zA-Z]?[_]*', '', subj_text)
                        subject = subj_text.strip(' ,-_')

                        if not subject:
                            continue

                        sh, sm = map(int, current_time_str[0].split(':'))
                        eh, em = map(int, current_time_str[1].split(':'))

                        start_dt = datetime.datetime(
                            current_date.year, current_date.month, current_date.day, sh, sm, tzinfo=TIMEZONE
                        )
                        end_dt = datetime.datetime(
                            current_date.year, current_date.month, current_date.day, eh, em, tzinfo=TIMEZONE
                        )

                        uid_key = f"{group_id}_{start_dt.isoformat()}_{subject}_{subgroup or 0}"
                        uid_hash = hashlib.md5(uid_key.encode('utf-8')).hexdigest()

                        display_summary = f"{subject} ({lesson_type})" if lesson_type else subject

                        lessons.append({
                            'uid': f"{uid_hash}@vyatsu.schedule",
                            'group_id': group_id,
                            'group_name': ginfo['name'],
                            'direction': ginfo.get('direction', 'pmib'),
                            'course': ginfo['course'],
                            'subject': subject,
                            'type': lesson_type,
                            'teacher': teacher,
                            'building': building,
                            'room': room,
                            'location': location,
                            'subgroup': subgroup,
                            'summary': display_summary,
                            'description': full_text,
                            'start': start_dt.isoformat(),
                            'end': end_dt.isoformat(),
                        })

    logging.info(f"[{ginfo['name']}] Из PDF извлечено занятий: {len(lessons)}")
    return lessons


def update_schedule():
    """Основной процесс обновления кэша и календарей для всех курсов направления."""
    cache = load_cache()
    try:
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=16, pool_maxsize=16, max_retries=3)
        session.mount('https://', adapter)
        session.mount('http://', adapter)
        resp = session.get(SCHEDULE_PAGE_URL, headers=HEADERS, timeout=25)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
    except Exception as e:
        logging.warning(f'Не удалось связаться с сайтом ВятГУ ({e}). Использую кэшированные данные.')
        soup = None

    has_changes = False

    # Динамический авто-поиск всех групп и направлений на странице расписания (Auto-Discovery)
    if soup:
        discovered_groups, discovered_dirs = discover_groups_and_directions(soup)
        if discovered_groups:
            logging.info(f"Auto-Discovery: обнаружено {len(discovered_groups)} актуальных групп и {len(discovered_dirs)} направлений всех ступеней на сайте ВятГУ.")
            if discovered_groups != SUPPORTED_GROUPS:
                save_groups(discovered_groups)
                SUPPORTED_GROUPS.clear()
                SUPPORTED_GROUPS.update(discovered_groups)
                has_changes = True
            if discovered_dirs != DIRECTIONS:
                save_directions(discovered_dirs)
                DIRECTIONS.clear()
                DIRECTIONS.update(discovered_dirs)
                has_changes = True
        else:
            logging.warning("Auto-Discovery не нашел групп по шаблону, используем сохраненные.")
    else:
        loaded = load_groups()
        if loaded:
            SUPPORTED_GROUPS.clear()
            SUPPORTED_GROUPS.update(loaded)
        loaded_dirs = load_directions()
        if loaded_dirs:
            DIRECTIONS.clear()
            DIRECTIONS.update(loaded_dirs)

    if soup:
        pdf_map = get_pdf_urls_map(soup)
        tasks = []
        for gid, ginfo in SUPPORTED_GROUPS.items():
            for start_date, url in pdf_map.get(gid, []):
                tasks.append((gid, ginfo['name'], start_date, url))

        etags = cache.setdefault('etags', {})

        def process_pdf_item(item):
            gid, gname, start_date, url = item
            req_headers = dict(HEADERS)
            cached_etag = etags.get(url)
            if url in cache['processed_urls'] and cached_etag:
                req_headers['If-None-Match'] = cached_etag

            try:
                resp = session.get(url, headers=req_headers, timeout=30)
                if resp.status_code == 304:
                    return None  # Файл не менялся
                resp.raise_for_status()
            except Exception as e:
                logging.warning(f"Ошибка скачивания {url}: {e}")
                return None

            content_hash = hashlib.sha256(resp.content).hexdigest()
            new_etag = resp.headers.get('ETag')
            if cache['processed_urls'].get(url) == content_hash:
                if new_etag and cached_etag != new_etag:
                    etags[url] = new_etag
                return None

            logging.info(f"[{gname}] Обнаружен новый или измененный PDF! Парсинг: {url}")
            try:
                new_lessons = parse_vyatsu_pdf(resp.content, start_date, group_id=gid)
                return (url, content_hash, new_etag, new_lessons)
            except Exception as e:
                logging.error(f"[{gname}] Ошибка парсинга PDF {url}: {e}")
                return None

        logging.info(f"Начало обработки {len(tasks)} PDF-расписаний с 8 потоками...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            for result in executor.map(process_pdf_item, tasks):
                if result:
                    url, content_hash, new_etag, new_lessons = result
                    for lesson in new_lessons:
                        cache['lessons'][lesson['uid']] = lesson
                    cache['processed_urls'][url] = content_hash
                    if new_etag:
                        etags[url] = new_etag
                    has_changes = True

    # Очистка устаревших пар: оставляем за последние 30 дней, все будущие и только для поддерживаемых групп
    threshold_date = (datetime.datetime.now(TIMEZONE) - datetime.timedelta(days=30)).isoformat()
    filtered_lessons = {
        uid: item for uid, item in cache['lessons'].items()
        if item.get('start', '') >= threshold_date and item.get('group_id', DEFAULT_GROUP_ID) in SUPPORTED_GROUPS and 'direction' in item
    }
    cache['lessons'] = filtered_lessons
    cache['processed_urls'] = {
        url: h for url, h in cache['processed_urls'].items()
        if any(f"Group/{gid}_" in url for gid in SUPPORTED_GROUPS)
    }
    if 'etags' in cache:
        cache['etags'] = {
            url: e for url, e in cache['etags'].items()
            if url in cache['processed_urls']
        }

    save_cache(cache)
    all_lessons = list(cache['lessons'].values())

    # Генерируем календари для каждой группы, разложенные по папкам
    valid_ics_files = set()
    for gid, ginfo in SUPPORTED_GROUPS.items():
        code = ginfo.get('code', gid)
        direction = ginfo.get('direction', 'pmib')
        dir_path = os.path.join(CALENDARS_DIR, direction)
        os.makedirs(dir_path, exist_ok=True)
        g_lessons = [l for l in all_lessons if l.get('group_id') == gid or (not l.get('group_id') and gid == DEFAULT_GROUP_ID)]

        f_all = os.path.join(dir_path, f'vyatsu_{code}.ics')
        f_sg1 = os.path.join(dir_path, f'vyatsu_{code}_sg1.ics')
        f_sg2 = os.path.join(dir_path, f'vyatsu_{code}_sg2.ics')

        valid_ics_files.update([os.path.abspath(f_all), os.path.abspath(f_sg1), os.path.abspath(f_sg2)])

        # Общий календарь группы
        generate_ics(g_lessons, f_all, title=f"Расписание ВятГУ {ginfo['name']}")

        # 1 подгруппа
        sg1 = [l for l in g_lessons if not l.get('subgroup') or l.get('subgroup') == 1]
        generate_ics(sg1, f_sg1, title=f"ВятГУ {ginfo['name']} (1 подгр.)")

        # 2 подгруппа
        sg2 = [l for l in g_lessons if not l.get('subgroup') or l.get('subgroup') == 2]
        generate_ics(sg2, f_sg2, title=f"ВятГУ {ginfo['name']} (2 подгр.)")

    # Удаляем устаревшие .ics файлы для групп, которых больше нет (выпустились или переименованы)
    for root, _, files in os.walk(CALENDARS_DIR):
        for f in files:
            if f.endswith('.ics'):
                full_p = os.path.abspath(os.path.join(root, f))
                if full_p not in valid_ics_files:
                    try:
                        os.remove(full_p)
                        logging.info(f"Удален устаревший календарь: {full_p}")
                        has_changes = True
                    except Exception as e:
                        logging.warning(f"Ошибка удаления {full_p}: {e}")

    return has_changes


def generate_ics(lessons, filename=ICS_FILE, title='Расписание ВятГУ ПМИб-1301'):
    """Генерирует стандартный .ics файл из списка занятий (RFC 5545)."""
    cal = Calendar()
    cal.creator = '-//Vyatsu//Schedule Bot//RU'
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    # Дедупликация занятий (по времени, предмету и подгруппе)
    unique_lessons = []
    seen = set()
    for item in lessons:
        key = (item['start'], item['end'], item.get('subject', item.get('summary')), item.get('subgroup'))
        if key not in seen:
            seen.add(key)
            unique_lessons.append(item)

    for item in unique_lessons:
        event = Event()
        event.uid = item['uid']
        event.name = item.get('summary', item.get('subject', 'Пара'))
        event.location = item.get('location', '')
        # Обязательные поля по стандарту RFC 5545 для Google и Apple календарей
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

    ics_text = cal.serialize()
    custom_headers = (
        "CALSCALE:GREGORIAN\r\n"
        "METHOD:PUBLISH\r\n"
        f"X-WR-CALNAME:{title}\r\n"
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

    dir_name = os.path.dirname(filename)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    tmp_file = f'{filename}.tmp'
    with open(tmp_file, 'w', encoding='utf-8') as f:
        f.write(ics_text)
    os.replace(tmp_file, filename)

    logging.info(f'Успешно сохранен календарь {filename} (всего пар: {len(lessons)})')


if __name__ == '__main__':
    update_schedule()
