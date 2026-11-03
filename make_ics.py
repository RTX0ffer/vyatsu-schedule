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
GROUP_ID = '27021'  # ПМИб-1301-52-01
TIMEZONE = ZoneInfo('Europe/Kirov')
CACHE_FILE = 'lessons_cache.json'
ICS_FILE = 'vyatsu.ics'

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


def get_group_pdf_urls():
    """Ищет на сайте ВятГУ актуальные PDF-файлы для группы."""
    logging.info('Запрос страницы расписания...')
    session = requests.Session()
    resp = session.get(SCHEDULE_PAGE_URL, headers=HEADERS, timeout=25)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')

    pattern = re.compile(rf'/reports/schedule/Group/{GROUP_ID}_\d+_(\d{{8}})_(\d{{8}})\.pdf')
    today = datetime.date.today()
    valid_urls = []

    for a_tag in soup.find_all('a', href=pattern):
        href = a_tag['href']
        match = pattern.search(href)
        if match:
            start_str, end_str = match.group(1), match.group(2)
            start_date = datetime.datetime.strptime(start_str, '%d%m%Y').date()
            end_date = datetime.datetime.strptime(end_str, '%d%m%Y').date()
            if end_date >= today:
                full_url = urljoin('https://old.vyatsu.ru', href)
                valid_urls.append((start_date, full_url))

    valid_urls.sort(key=lambda x: x[0])
    logging.info(f'Найдено актуальных PDF ссылок: {len(valid_urls)}')
    return valid_urls


def parse_vyatsu_pdf(pdf_bytes, start_date_hint):
    """Разбирает байты PDF расписания ВятГУ и достает структурированный список занятий."""
    time_pattern = re.compile(r'(\d{1,2}:\d{2})\s*[-–—]\s*(\d{1,2}:\d{2})')
    lessons = []

    current_day_offset = -1
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

                    # Начало нового дня
                    if day_cell and 'День' not in day_cell:
                        current_day_offset += 1
                        current_date = start_date_hint + datetime.timedelta(days=current_day_offset)

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

                        # 2. Очищаем от номера группы
                        clean_text = re.sub(r'ПМИб-\d+-\d+-\d+,?\s*', '', full_text)

                        # 3. Извлекаем корпус и аудиторию
                        room_m = re.search(r'\b(\d{1,2})-(\d{2,4}[а-яА-Яa-zA-Z]?)\b', clean_text)
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
                        type_m = re.search(r'\b(Лекция|Практическое занятие|Лабораторная работа)\b', clean_text)
                        lesson_type = type_m.group(1) if type_m else ''

                        # 5. Извлекаем ФИО преподавателя
                        teacher_m = re.search(r'([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ]\.\s*[А-ЯЁ]\.|\s+[А-ЯЁ]\.))', clean_text)
                        teacher = teacher_m.group(1) if teacher_m else ''

                        # 6. Извлекаем чистое название предмета
                        subj_text = clean_text
                        if sg_match:
                            subj_text = re.sub(r'^\d+\s*подгруппа,?\s*', '', subj_text)
                        if lesson_type:
                            subj_text = subj_text.split(lesson_type)[0]
                        subject = subj_text.strip(' ,-')

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

                        uid_key = f"{start_dt.isoformat()}_{subject}_{subgroup or 0}"
                        uid_hash = hashlib.md5(uid_key.encode('utf-8')).hexdigest()

                        display_summary = f"{subject} ({lesson_type})" if lesson_type else subject

                        lessons.append({
                            'uid': f"{uid_hash}@vyatsu.schedule",
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

    logging.info(f'Из PDF извлечено занятий: {len(lessons)}')
    return lessons


def update_schedule():
    """Основной процесс обновления кэша и календаря."""
    cache = load_cache()
    items = get_group_pdf_urls()

    if not items:
        logging.warning('Не найдено ссылок на расписание. Календарь не обновлен.')
        return False

    has_changes = False

    for start_date, url in items:
        logging.info(f'Проверяю: {url} (старт: {start_date})')
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        content_hash = hashlib.sha256(resp.content).hexdigest()

        if cache['processed_urls'].get(url) == content_hash and cache['lessons']:
            logging.info('Файл не изменился (кэш совпадает).')
            continue

        logging.info('Обнаружен новый или измененный PDF! Парсинг...')
        new_lessons = parse_vyatsu_pdf(resp.content, start_date)
        for lesson in new_lessons:
            cache['lessons'][lesson['uid']] = lesson

        cache['processed_urls'][url] = content_hash
        has_changes = True

    # Очистка устаревших пар: оставляем за последние 30 дней и все будущие
    threshold_date = (datetime.datetime.now(TIMEZONE) - datetime.timedelta(days=30)).isoformat()
    filtered_lessons = {
        uid: item for uid, item in cache['lessons'].items()
        if item['start'] >= threshold_date
    }
    cache['lessons'] = filtered_lessons

    save_cache(cache)
    generate_ics(cache['lessons'].values())
    return has_changes


def generate_ics(lessons, filename=ICS_FILE):
    """Генерирует стандартный .ics файл из списка занятий (RFC 5545)."""
    cal = Calendar()
    cal.creator = 'Vyatsu Schedule Bot'
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    for item in lessons:
        event = Event()
        event.uid = item['uid']
        event.name = item.get('summary', item.get('subject', 'Пара'))
        event.location = item.get('location', '')
        # Обязательное поле DTSTAMP для Google и Apple календарей
        event.created = now_utc

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
        "X-WR-CALNAME:Расписание ВятГУ ПМИб-1301\r\n"
        "X-WR-TIMEZONE:Europe/Kirov\r\n"
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H\r\n"
        "X-PUBLISHED-TTL:PT6H\r\n"
    )
    if "BEGIN:VCALENDAR\r\n" in ics_text:
        ics_text = ics_text.replace("BEGIN:VCALENDAR\r\n", f"BEGIN:VCALENDAR\r\n{custom_headers}")
    else:
        ics_text = ics_text.replace("BEGIN:VCALENDAR\n", f"BEGIN:VCALENDAR\n{custom_headers}")

    tmp_file = f'{filename}.tmp'
    with open(tmp_file, 'w', encoding='utf-8') as f:
        f.write(ics_text)
    os.replace(tmp_file, filename)

    logging.info(f'Успешно сохранен календарь {filename} (всего пар: {len(lessons)})')


if __name__ == '__main__':
    update_schedule()
