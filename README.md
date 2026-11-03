# Автоматическое расписание ВятГУ 📅

Автоматический парсинг двухнедельного расписания с сайта ВятГУ, ежедневное ночное обновление календаря (.ics) через GitHub Actions и Telegram-бот.

## 🚀 Как это устроено
1. **GitHub Actions** каждую полночь в 00:00 (МСК) запускает [`make_ics.py`](make_ics.py).
2. Скрипт скачивает актуальные PDF, парсит занятия и обновляет `lessons_cache.json` и `vyatsu.ics`.
3. Файлы коммитятся обратно в репозиторий.
4. **Смартфон** автоматически обновляет календарь по ссылке на `vyatsu.ics`.
5. **Telegram-бот** подтягивает данные из `lessons_cache.json` по сети и мгновенно отвечает на запросы студентов.

---

## 📲 Как подписаться на календарь со смартфона

Ваша ссылка:
```
https://raw.githubusercontent.com/<ВАШ_GITHUB_ЛОГИН>/<ИМЯ_РЕПОЗИТОРИЯ>/main/vyatsu.ics
```

### iPhone (Apple Calendar):
1. Откройте Safari и вставьте ссылку с протоколом `webcal://`:
   `webcal://raw.githubusercontent.com/<ЛОГИН>/<РЕПОЗИТОРИЙ>/main/vyatsu.ics`
2. Нажмите «Подписаться» и укажите автообновление (например, раз в день).

### Android / Google Календарь:
1. Зайдите в браузерную версию [Google Календаря](https://calendar.google.com/) с компьютера.
2. Слева в блоке «Другие календари» нажмите **«+»** ➔ **«Добавить по URL»**.
3. Вставьте ссылку `https://raw.githubusercontent.com/.../vyatsu.ics` и нажмите «Добавить календарь».
4. В приложении Google Календарь на телефоне включите синхронизацию этого календаря.

---

## ⚙️ Настройка GitHub Actions

1. Создайте репозиторий на GitHub и загрузите файлы:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/<ВАШ_ЛОГИН>/<ВАШ_РЕПОЗИТОРИЙ>.git
   git push -u origin main
   ```
2. **Важно! Включите права на запись для GitHub Actions:**
   * Откройте ваш репозиторий на GitHub ➔ **Settings** ➔ **Actions** ➔ **General**.
   * Прокрутите до раздела **Workflow permissions**.
   * Выберите **Read and write permissions** и нажмите **Save**.
3. *(Опционально)* Если хотите получать уведомления в Telegram при изменениях:
   * Перейдите в **Settings** ➔ **Secrets and variables** ➔ **Actions**.
   * Добавьте Secrets:
     - `TELEGRAM_BOT_TOKEN`: токен вашего бота от `@BotFather`
     - `TELEGRAM_CHAT_ID`: ваш ID в Telegram (можно узнать у бота `@userinfobot`).

---

## 🤖 Запуск Telegram-бота (по желанию)

Бот умеет отвечать на команды:
- `/today` — пары на сегодня
- `/tomorrow` — пары на завтра
- `/week` — расписание на неделю
- `/calendar` — ссылка на подписку

### Локальный запуск или запуск на сервере:
```bash
pip install -r requirements.txt
export BOT_TOKEN="ВАШ_ТОКЕН_ОТ_BOTFATHER"
export ICS_URL="https://raw.githubusercontent.com/<ЛОГИН>/<РЕПОЗИТОРИЙ>/main/vyatsu.ics"
python bot.py
```
Бот мгновенно берет готовые данные из `lessons_cache.json`, поэтому не тратит время и ресурсы на повторный парсинг PDF.
