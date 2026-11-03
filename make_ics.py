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
    valid_urls = set()

    for a_tag in soup.find_all('a', href=pattern):
        href = a_tag['href']
        match = pattern.search(href)
        if match:
            start_str, end_str = match.group(1), match.group(2)
            end_date = datetime.datetime.strptime(end_str, '%d%m%Y').date()
            # Берем файлы, период которых заканчивается сегодня или позже
            if end_date >= today:
                full_url = urljoin('https://old.vyatsu.ru', href)
                valid_urls.add((start_str, full_url))

    sorted_urls = [url for _, url in sorted(valid_urls)]
    logging.info(f'Найдено актуальных PDF ссылок: {len(sorted_urls)}')
    return sorted_urls


def parse_vyatsu_pdf(pdf_bytes):
    """Разбирает байты PDF и достает список занятий."""
    lessons = []
    current_date = None

    date_pattern = re.compile(r'(\d{2}\.\d{2}\.\d{2,4})')
    time_pattern = re.compile(r'(\d{1,2}[:.]\d{2})\s*[-–—]\s*(\d{1,2}[:.]\d{2})')

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables() or []
            for table in tables:
                for row in table:
                    cells = [c.strip() if c else '' for c in row]
                    row_joined = ' '.join(cells)

                    date_match = date_pattern.search(row_joined)
                    if date_match:
                        d_str = date_match.group(1)
                        fmt = '%d.%m.%Y' if len(d_str) == 10 else '%d.%m.%y'
                        current_date = datetime.datetime.strptime(d_str, fmt).date()

                    time_match = time_pattern.search(row_joined)
                    if current_date and time_match:
                        start_t = time_match.group(1).replace('.', ':')
                        end_t = time_match.group(2).replace('.', ':')

                        subject_cells = [
                            c for c in cells
                            if c and not date_pattern.search(c) and not time_pattern.search(c)
                        ]
                        subject_text = ' '.join(subject_cells).strip()

                        if not subject_text or 'Дисциплина' in subject_text or 'Время' in subject_text:
                            continue

                        lines = [line.strip() for line in subject_text.split('\n') if line.strip()]
                        full_text = ' '.join(lines)
                        room_match = re.search(r'(\d{1,2}-\d{2,4}[а-яА-Яa-zA-Z]?|[Сс]портзал.*)', full_text)
                        room = room_match.group(1) if room_match else ''

                        sh, sm = map(int, start_t.split(':'))
                        eh, em = map(int, end_t.split(':'))

                        start_dt = datetime.datetime(
                            current_date.year, current_date.month, current_date.day, sh, sm, tzinfo=TIMEZONE
                        )
                        end_dt = datetime.datetime(
                            current_date.year, current_date.month, current_date.day, eh, em, tzinfo=TIMEZONE
                        )

                        # Уникальный ключ занятия: дата_время_предмет
                        uid_key = f"{start_dt.isoformat()}_{lines[0] if lines else full_text}"
                        uid_hash = hashlib.md5(uid_key.encode('utf-8')).hexdigest()

                        lessons.append({
                            'uid': f"{uid_hash}@vyatsu.schedule",
                            'summary': lines[0] if lines else full_text,
                            'description': full_text,
                            'location': f'ВятГУ, ауд. {room}' if room else 'ВятГУ',
                            'start': start_dt.isoformat(),
                            'end': end_dt.isoformat(),
                        })
    return lessons


def update_schedule():
    """Основной процесс обновления кэша и календаря."""
    cache = load_cache()
    urls = get_group_pdf_urls()

    if not urls:
        logging.warning('Не найдено ссылок на расписание. Календарь не обновлен.')
        return False

    has_changes = False

    for url in urls:
        logging.info(f'Проверяю: {url}')
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        content_hash = hashlib.sha256(resp.content).hexdigest()

        # Если файл уже скачивался с этим же содержимым — пропускаем парсинг
        if cache['processed_urls'].get(url) == content_hash:
            logging.info('Файл не изменился (кэш совпадает).')
            continue

        logging.info('Обнаружен новый или измененный PDF! Парсинг...')
        new_lessons = parse_vyatsu_pdf(resp.content)
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
    """Генерирует стандартный .ics файл из списка занятий."""
    cal = Calendar()
    cal.creator = 'Vyatsu Schedule Bot'

    for item in lessons:
        event = Event()
        event.uid = item['uid']
        event.name = item['summary']
        event.location = item.get('location', '')
        event.description = item.get('description', '')
        event.begin = datetime.datetime.fromisoformat(item['start'])
        event.end = datetime.datetime.fromisoformat(item['end'])
        cal.events.add(event)

    # Добавляем полезные метаданные для календарных клиентов
    ics_text = cal.serialize()
    custom_headers = (
        "X-WR-CALNAME:Расписание ВятГУ\n"
        "X-WR-TIMEZONE:Europe/Kirov\n"
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H\n"
        "X-PUBLISHED-TTL:PT6H\n"
    )
    ics_text = ics_text.replace("BEGIN:VCALENDAR\n", f"BEGIN:VCALENDAR\n{custom_headers}")

    tmp_file = f'{filename}.tmp'
    with open(tmp_file, 'w', encoding='utf-8') as f:
        f.write(ics_text)
    os.replace(tmp_file, filename)

    logging.info(f'Успешно сохранен календарь {filename} (всего пар: {len(lessons)})')


if __name__ == '__main__':
    update_schedule()
