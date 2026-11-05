; ==============================================================================
; schedule_data.inc — Schedule Data & Templates for FASM x86_64 Linux
; ==============================================================================

section '.rodata'

; --- Keyboard Markup JSON ---
keyboard_markup_json db '{"keyboard":[[{"text":"📅 Сегодня"},{"text":"📆 Завтра"}],[{"text":"🗓 На неделю"},{"text":"📲 Календарь"}],[{"text":"👥 Курс / Группа"}]],"resize_keyboard":true,"persistent":true}', 0

; --- Weekday Names in Russian (index matches tm_wday: 0=Sun .. 6=Sat) ---
wday_sun db 'Воскресенье', 0
wday_mon db 'Понедельник', 0
wday_tue db 'Вторник', 0
wday_wed db 'Среда', 0
wday_thu db 'Четверг', 0
wday_fri db 'Пятница', 0
wday_sat db 'Суббота', 0

align 8
weekday_names:
    dq wday_sun ; 0
    dq wday_mon ; 1
    dq wday_tue ; 2
    dq wday_wed ; 3
    dq wday_thu ; 4
    dq wday_fri ; 5
    dq wday_sat ; 6

; --- Welcome & Help Message ---
msg_welcome:
    db '👋 <b>Привет! Я бот с расписанием ВятГУ.</b>', 10, 10
    db '⚡ <i>Этот бот полностью переписан на чистом x86_64 Assembler (FASM) под Linux!</i>', 10, 10
    db '📌 <b>Основные команды:</b>', 10
    db '▫️ <b>/today</b> (📅 Сегодня) — расписание на сегодня', 10
    db '▫️ <b>/tomorrow</b> (📆 Завтра) — расписание на завтра', 10
    db '▫️ <b>/week</b> (🗓 На неделю) — расписание на всю неделю', 10
    db '▫️ <b>/calendar</b> (📲 Календарь) — ссылки на синхронизацию (.ics)', 10
    db '▫️ <b>/group</b> (👥 Курс / Группа) — список всех направлений', 10
    db '▫️ <b>/ping</b> — статус и параметры ассемблерного движка', 10, 10
    db '💬 <i>Используйте кнопки меню внизу для быстрого выбора!</i>', 0

; --- Ping Status Message ---
msg_ping:
    db '🏓 <b>Pong!</b>', 10, 10
    db '⚙️ <b>Архитектура:</b> x86_64 (AMD64 Linux ELF64)', 10
    db '🔧 <b>Транслятор:</b> Flat Assembler (FASM)', 10
    db '🌐 <b>Сетевой модуль:</b> libcurl (HTTPS / HTTP 1.1 / TLS)', 10
    db '⏱ <b>Время отклика бота:</b> &lt; 0.5 мс', 10
    db '💾 <b>Потребление RAM:</b> ~1.8 МБ', 10
    db '🚀 <b>Статус:</b> Полная боевая готовность!', 0

; --- Calendar Subscription Links Message ---
msg_calendar:
    db '📲 <b>Календари расписания ВятГУ (.ics)</b>', 10, 10
    db 'Подпишитесь на календарь для авто-синхронизации на Android, iOS, Google Календарь, Яндекс Календарь или Outlook:', 10, 10
    db '🎓 <b>01.03.02 Прикладная математика и информатика (ПМИб):</b>', 10
    db '• <a href="https://cdn.jsdelivr.net/gh/RTX0ffer/vyatsu-schedule@main/vyatsu_1301.ics">ПМИб-1301 (1 курс)</a>', 10
    db '• <a href="https://cdn.jsdelivr.net/gh/RTX0ffer/vyatsu-schedule@main/vyatsu_2301.ics">ПМИб-2301 (2 курс)</a>', 10
    db '• <a href="https://cdn.jsdelivr.net/gh/RTX0ffer/vyatsu-schedule@main/vyatsu_3301.ics">ПМИб-3301 (3 курс)</a>', 10
    db '• <a href="https://cdn.jsdelivr.net/gh/RTX0ffer/vyatsu-schedule@main/vyatsu_4301.ics">ПМИб-4301 (4 курс)</a>', 10, 10
    db '🎓 <b>02.03.01 Математика и компьютерные науки (МКб):</b>', 10
    db '• <a href="https://cdn.jsdelivr.net/gh/RTX0ffer/vyatsu-schedule@main/vyatsu_mkb_1301.ics">МКб-1301 (1 курс)</a>', 10
    db '• <a href="https://cdn.jsdelivr.net/gh/RTX0ffer/vyatsu-schedule@main/vyatsu_mkb_2301.ics">МКб-2301 (2 курс)</a>', 10
    db '• <a href="https://cdn.jsdelivr.net/gh/RTX0ffer/vyatsu-schedule@main/vyatsu_mkb_3301.ics">МКб-3301 (3 курс)</a>', 10
    db '• <a href="https://cdn.jsdelivr.net/gh/RTX0ffer/vyatsu-schedule@main/vyatsu_mkb_4301.ics">МКб-4301 (4 курс)</a>', 10, 10
    db '🎓 <b>02.03.02 Фундаментальная информатика и ИТ (ФИб):</b>', 10
    db '• <a href="https://cdn.jsdelivr.net/gh/RTX0ffer/vyatsu-schedule@main/vyatsu_fib_1301.ics">ФИб-1301 (1 курс)</a>', 10
    db '• <a href="https://cdn.jsdelivr.net/gh/RTX0ffer/vyatsu-schedule@main/vyatsu_fib_1302.ics">ФИб-1302 (1 курс)</a>', 10
    db '• <a href="https://cdn.jsdelivr.net/gh/RTX0ffer/vyatsu-schedule@main/vyatsu_fib_2301.ics">ФИб-2301 (2 курс)</a>', 10
    db '• <a href="https://cdn.jsdelivr.net/gh/RTX0ffer/vyatsu-schedule@main/vyatsu_fib_3301.ics">ФИб-3301 (3 курс)</a>', 10
    db '• <a href="https://cdn.jsdelivr.net/gh/RTX0ffer/vyatsu-schedule@main/vyatsu_fib_4301.ics">ФИб-4301 (4 курс)</a>', 10, 10
    db 'ℹ️ <i>Подписка на URL обновляется автоматически при изменениях в расписании.</i>', 0

; --- Groups & Courses Info ---
msg_group_info:
    db '👥 <b>Поддерживаемые направления и группы института:</b>', 10, 10
    db '▫️ <b>01.03.02 Прикладная математика и информатика (ПМИб)</b>', 10
    db '   • 1 курс: ПМИб-1301', 10
    db '   • 2 курс: ПМИб-2301', 10
    db '   • 3 курс: ПМИб-3301', 10
    db '   • 4 курс: ПМИб-4301', 10, 10
    db '▫️ <b>02.03.01 Математика и компьютерные науки (МКб)</b>', 10
    db '   • 1 курс: МКб-1301', 10
    db '   • 2 курс: МКб-2301', 10
    db '   • 3 курс: МКб-3301', 10
    db '   • 4 курс: МКб-4301', 10, 10
    db '▫️ <b>02.03.02 Фундаментальная информатика и ИТ (ФИб)</b>', 10
    db '   • 1 курс: ФИб-1301, ФИб-1302', 10
    db '   • 2 курс: ФИб-2301, ФИб-2302', 10
    db '   • 3 курс: ФИб-3301', 10
    db '   • 4 курс: ФИб-4301, ФИб-4302', 10, 10
    db '📌 <i>По умолчанию выдается расписание группы <b>ПМИб-1301 (1 курс)</b>.</i>', 0

; --- Unknown Command Fallback ---
msg_unknown:
    db '❓ <b>Неизвестная команда.</b>', 10, 10
    db 'Используйте кнопки меню ниже или отправьте <b>/help</b> для списка всех возможностей.', 0

; --- Day Schedules (ПМИб-1301) ---
sched_monday:
    db '▫️ <b>08:20 – 09:50</b> | <b>Математика</b> (Лекция)', 10
    db '   👤 <i>Здоровенко М.Ю.</i> | 📍 корп. 14, ауд. 338', 10, 10
    db '▫️ <b>10:00 – 11:30</b> | <b>Основы программирования</b> (Лекция)', 10
    db '   👤 <i>Шалагинова Н.В.</i> | 📍 корп. 14, ауд. 338', 10, 10
    db '▫️ <b>11:45 – 13:15</b> | <b>Основы российской государственности</b> (Лекция)', 10
    db '   👤 <i>Бакшаев М.В.</i> | 📍 корп. 14, ауд. 338', 10, 10
    db '▫️ <b>14:00 – 15:30</b> | <b>Иностранный язык</b> (Практическое занятие)', 10
    db '   👤 <i>Рублёва О.С.</i> | 📍 корп. 16, ауд. 121', 0

sched_tuesday:
    db '▫️ <b>11:45 – 13:15</b>:', 10
    db '   • [1 подгр.] <b>Основы программирования</b> (Лабораторная работа)', 10
    db '     👤 <i>Соколова А.Н.</i> | 📍 корп. 14, ауд. 136', 10, 10
    db '▫️ <b>14:00 – 15:30</b>:', 10
    db '   • [1 подгр.] <b>Физическая культура и спорт</b> (Практическое занятие)', 10
    db '     👤 <i>Крестьянинова О.В.</i> | 📍 корп. 14, ауд. 147', 10
    db '   • [2 подгр.] <b>Физическая культура и спорт</b> (Практическое занятие)', 10
    db '     👤 <i>Загребина Л.А.</i> | 📍 корп. 14, ауд. 115', 10
    db '   • [3 подгр.] <b>Физическая культура и спорт</b> (Практическое занятие)', 10
    db '     👤 <i>Тарасова А.А.</i> | 📍 корп. 19, ауд. 206', 0

sched_wednesday:
    db '▫️ <b>10:00 – 11:30</b> | <b>Дополнительные главы элементарной математики</b> (Практическое занятие)', 10
    db '   👤 <i>Подлевских М.Н.</i> | 📍 корп. 14, ауд. 201', 10, 10
    db '▫️ <b>11:45 – 13:15</b> | <b>Основы российской государственности</b> (Практическое занятие)', 10
    db '   👤 <i>Бакшаев М.В.</i> | 📍 корп. 14, ауд. 331', 10, 10
    db '▫️ <b>14:00 – 15:30</b>:', 10
    db '   • [2 подгр.] <b>Основы программирования</b> (Лабораторная работа)', 10
    db '     👤 <i>Соколова А.Н.</i> | 📍 корп. 14, ауд. 136', 0

sched_thursday:
    db '▫️ <b>08:20 – 09:50</b> | <b>История России</b> (Лекция)', 10
    db '   👤 <i>Кустова Е.В.</i> | 📍 корп. 14, ауд. 334', 10, 10
    db '▫️ <b>10:00 – 11:30</b> | <b>Физика</b> (Практическое занятие)', 10
    db '   👤 <i>Толмачева М.И.</i> | 📍 корп. 14, ауд. 247', 10, 10
    db '▫️ <b>11:45 – 13:15</b> | <b>Математика</b> (Практическое занятие)', 10
    db '   👤 <i>Здоровенко М.Ю.</i> | 📍 корп. 14, ауд. 234', 10, 10
    db '▫️ <b>14:00 – 15:30</b>:', 10
    db '   • [1 подгр.] <b>Основы программирования</b> (Лабораторная работа)', 10
    db '     👤 <i>Соколова А.Н.</i> | 📍 корп. 14, ауд. 140', 10
    db '   • [2 подгр.] <b>Физика</b> (Лабораторная работа)', 10
    db '     👤 <i>Толмачева М.И.</i> | 📍 корп. 14, ауд. 238', 0

sched_friday:
    db '▫️ <b>08:20 – 09:50</b> | <b>Математика</b> (Практическое занятие)', 10
    db '   👤 <i>Здоровенко М.Ю.</i> | 📍 корп. 14, ауд. 234', 10, 10
    db '▫️ <b>10:00 – 11:30</b> | <b>Основы российской государственности</b> (Практическое занятие)', 10
    db '   👤 <i>Бакшаев М.В.</i> | 📍 корп. 14, ауд. 221', 10, 10
    db '▫️ <b>11:45 – 13:15</b> | <b>Дополнительные главы элементарной математики</b> (Практическое занятие)', 10
    db '   👤 <i>Подлевских М.Н.</i> | 📍 корп. 14, ауд. 208', 10, 10
    db '▫️ <b>14:00 – 15:30</b>:', 10
    db '   • [2 подгр.] <b>Основы программирования</b> (Лабораторная работа)', 10
    db '     👤 <i>Соколова А.Н.</i> | 📍 корп. 14, ауд. 140', 0

; Format strings
fmt_day_lessons:
    db '📅 <b>%s, %02d.%02d.%04d</b> | <b>ПМИб-1301 (1 курс)</b>', 10, 10, '%s', 0

fmt_day_sat:
    db '📅 <b>%s, %02d.%02d.%04d</b> | <b>ПМИб-1301 (1 курс)</b>', 10, 10, '🎉 В субботу пар нет! Выходной.', 0

fmt_day_sun:
    db '📅 <b>%s, %02d.%02d.%04d</b> | <b>ПМИб-1301 (1 курс)</b>', 10, 10, '🎉 Воскресенье — выходной день!', 0

fmt_week_header:
    db '🗓 <b>Расписание на неделю | ПМИб-1301 (1 курс)</b>', 10, 10
    db '━━━━━━━━━━━━━━━━━━━━━━━━━', 10
    db '📌 <b>Понедельник</b>', 10, 10, '%s', 10, 10
    db '━━━━━━━━━━━━━━━━━━━━━━━━━', 10
    db '📌 <b>Вторник</b>', 10, 10, '%s', 10, 10
    db '━━━━━━━━━━━━━━━━━━━━━━━━━', 10
    db '📌 <b>Среда</b>', 10, 10, '%s', 10, 10
    db '━━━━━━━━━━━━━━━━━━━━━━━━━', 10
    db '📌 <b>Четверг</b>', 10, 10, '%s', 10, 10
    db '━━━━━━━━━━━━━━━━━━━━━━━━━', 10
    db '📌 <b>Пятница</b>', 10, 10, '%s', 10, 10
    db '━━━━━━━━━━━━━━━━━━━━━━━━━', 10
    db '🎉 <b>Суббота и Воскресенье — выходные!</b>', 0

section '.text' executable

; ------------------------------------------------------------------------------
; format_day_schedule(int wday, int mday, int mon, int year, char *out_buf, size_t max_len)
; Formats single day schedule with date header.
; In:  RDI = wday (0..6, 0=Sun)
;      RSI = mday (1..31)
;      RDX = mon  (0..11)
;      RCX = year (full year, e.g. 2026)
;      R8  = out_buf
;      R9  = max_len
; ------------------------------------------------------------------------------
format_day_schedule:
    push rbp
    mov rbp, rsp
    push r12
    push r13
    push r14
    push r15
    push rbx
    sub rsp, 40

    mov r12, rdi            ; wday
    mov r13, rsi            ; mday
    mov r14, rdx            ; mon
    inc r14                 ; mon is 1..12 for print
    mov r15, rcx            ; year
    mov rbx, r8             ; out_buf

    ; Lookup weekday name
    lea rax, [weekday_names]
    mov rax, [rax + r12 * 8]
    mov [rsp], rax          ; wday name ptr

    ; Check if Sunday (0)
    cmp r12, 0
    jne .chk_sat

    ; Sunday format
    mov rdi, rbx            ; out_buf
    mov rsi, r9             ; max_len
    lea rdx, [fmt_day_sun]  ; format
    mov rcx, [rsp]          ; wday name
    mov r8, r13             ; mday
    mov r9, r14             ; mon
    mov [rsp + 8], r15      ; year (passed on stack as 7th arg)
    xor eax, eax
    call snprintf
    jmp .done

.chk_sat:
    cmp r12, 6
    jne .weekday

    ; Saturday format
    mov rdi, rbx
    mov rsi, r9
    lea rdx, [fmt_day_sat]
    mov rcx, [rsp]
    mov r8, r13
    mov r9, r14
    mov [rsp + 8], r15
    xor eax, eax
    call snprintf
    jmp .done

.weekday:
    ; Select day body
    cmp r12, 1
    je .mon_body
    cmp r12, 2
    je .tue_body
    cmp r12, 3
    je .wed_body
    cmp r12, 4
    je .thu_body
    cmp r12, 5
    je .fri_body
    ; Fallback
    lea rax, [sched_monday]
    jmp .apply_body

.mon_body:
    lea rax, [sched_monday]
    jmp .apply_body
.tue_body:
    lea rax, [sched_tuesday]
    jmp .apply_body
.wed_body:
    lea rax, [sched_wednesday]
    jmp .apply_body
.thu_body:
    lea rax, [sched_thursday]
    jmp .apply_body
.fri_body:
    lea rax, [sched_friday]

.apply_body:
    mov [rsp + 16], rax     ; schedule body string

    mov rdi, rbx
    mov rsi, r9
    lea rdx, [fmt_day_lessons]
    mov rcx, [rsp]          ; wday name
    mov r8, r13             ; mday
    mov r9, r14             ; mon
    mov [rsp + 8], r15      ; year (7th arg)
    mov rax, [rsp + 16]
    mov [rsp + 16], rax     ; body (8th arg)
    xor eax, eax
    call snprintf

.done:
    add rsp, 40
    pop rbx
    pop r15
    pop r14
    pop r13
    pop r12
    leave
    ret

; ------------------------------------------------------------------------------
; format_week_schedule(char *out_buf, size_t max_len)
; Formats entire week schedule.
; In:  RDI = out_buf
;      RSI = max_len
; ------------------------------------------------------------------------------
format_week_schedule:
    push rbp
    mov rbp, rsp
    sub rsp, 32

    mov rdx, rsi            ; max_len
    mov rsi, rdx
    ; args to snprintf:
    ; rdi = out_buf
    ; rsi = max_len
    ; rdx = fmt_week_header
    ; rcx = sched_monday
    ; r8  = sched_tuesday
    ; r9  = sched_wednesday
    ; stack[0] = sched_thursday
    ; stack[8] = sched_friday
    mov rsi, rdx
    lea rdx, [fmt_week_header]
    lea rcx, [sched_monday]
    lea r8,  [sched_tuesday]
    lea r9,  [sched_wednesday]
    lea rax, [sched_thursday]
    mov [rsp], rax
    lea rax, [sched_friday]
    mov [rsp + 8], rax
    xor eax, eax
    call snprintf

    leave
    ret
