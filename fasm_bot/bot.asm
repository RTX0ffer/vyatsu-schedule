; ==============================================================================
; bot.asm — High-Performance Telegram Schedule Bot in x86_64 FASM for Linux
; ==============================================================================
; Architecture : x86_64 (ELF64)
; Assembler    : Flat Assembler (FASM)
; Network      : libcurl (HTTPS long-polling & JSON POST)
; C Library    : glibc (standard POSIX calls)
; Target OS    : Linux (Ubuntu, Debian, Fedora, Arch, CentOS, Alpine/glibc, etc.)
; ==============================================================================

format ELF64

public main

; --- External C Library Functions ---
extrn printf
extrn puts
extrn getenv
extrn snprintf
extrn malloc
extrn realloc
extrn free
extrn memcpy
extrn memset
extrn strlen
extrn strcmp
extrn strncmp
extrn strstr
extrn strchr
extrn sleep
extrn usleep
extrn time
extrn localtime
extrn exit

; --- External Libcurl Functions ---
extrn curl_global_init
extrn curl_global_cleanup
extrn curl_easy_init
extrn curl_easy_setopt
extrn curl_easy_perform
extrn curl_easy_cleanup
extrn curl_easy_strerror
extrn curl_slist_append
extrn curl_slist_free_all

; --- Include Bot Modules ---
include 'http_client.inc'
include 'json_helper.inc'
include 'schedule_data.inc'

section '.data' writeable

bot_token_env_var   db 'BOT_TOKEN', 0
curl_handle         dq 0
last_offset         dq 0
current_time        dq 0
target_time         dq 0
temp_chat_id        dq 0
temp_update_id      dq 0

; Buffers
align 16
resp_buf            rb BUF_STRUCT_SIZE
post_resp_buf       rb BUF_STRUCT_SIZE
bot_token           rb 256
req_url             rb 1024
send_url            rb 1024
msg_text_buf        rb 4096
escaped_text_buf    rb 32768
post_payload        rb 65536
msg_reply_buf       rb 16384

section '.rodata'

; --- Startup Banner & Logs ---
banner_str:
    db 10
    db '==============================================================', 10
    db '  🚀 Telegram Schedule Bot (FASM x86_64 Linux)', 10
    db '  ⚡ Чистый ассемблер x86_64 | Flat Assembler | libcurl | libc', 10
    db '  🎓 Направление: ВятГУ (ПМИб, МКб, ФИб)', 10
    db '==============================================================', 10, 0

log_token_ok    db '[INFO] BOT_TOKEN успешно загружен из окружения.', 10, 0
log_init_ok     db '[INFO] Сетевой модуль libcurl инициализирован.', 10, 0
log_polling     db '[INFO] Запуск long-polling цикла (getUpdates)...', 10, 0
log_update      db '[UPDATE] Update #%ld | Chat ID: %ld | Текст: "%s"', 10, 0
log_sent        db '[SUCCESS] Ответ успешно отправлен в чат %ld', 10, 0
log_net_err     db '[WARN] Ошибка сети при getUpdates (код %ld). Повтор через 3 сек...', 10, 0
log_send_err    db '[ERROR] Ошибка отправки сообщения (код %ld)', 10, 0

err_token_msg:
    db 10
    db '❌ [ОШИБКА] Переменная окружения BOT_TOKEN не установлена!', 10, 10
    db '   Задайте её перед запуском бота командой:', 10
    db '       export BOT_TOKEN="ваш_токен_от_BotFather"', 10
    db '       ./bot', 10, 10, 0

; URL & Payload Format Strings
fmt_get_updates db 'https://api.telegram.org/bot%s/getUpdates?offset=%ld&timeout=25', 0
fmt_send_msg    db 'https://api.telegram.org/bot%s/sendMessage', 0
fmt_post_json   db '{"chat_id": %ld, "text": "%s", "parse_mode": "HTML", "reply_markup": %s}', 0

; JSON Keys
key_ok          db 'ok', 0
key_result      db 'result', 0
key_update_id   db 'update_id', 0
key_chat        db 'chat', 0
key_id          db 'id', 0
key_text        db 'text', 0

; Command Strings
cmd_start       db '/start', 0
cmd_help        db '/help', 0
cmd_today       db '/today', 0
cmd_tomorrow    db '/tomorrow', 0
cmd_week        db '/week', 0
cmd_calendar    db '/calendar', 0
cmd_group       db '/group', 0
cmd_ping        db '/ping', 0

; Button Text Strings (UTF-8)
btn_today       db '📅 Сегодня', 0
btn_tomorrow    db '📆 Завтра', 0
btn_week        db '🗓 На неделю', 0
btn_calendar    db '📲 Календарь', 0
btn_group       db '👥 Курс / Группа', 0

section '.text' executable

; ------------------------------------------------------------------------------
; main() — Bot Entry Point
; ------------------------------------------------------------------------------
main:
    push rbp
    mov rbp, rsp
    sub rsp, 32

    ; Print Startup Banner
    lea rdi, [banner_str]
    xor eax, eax
    call printf

    ; 1. Read BOT_TOKEN from environment
    lea rdi, [bot_token_env_var]
    call getenv
    test rax, rax
    jz .err_no_token
    cmp byte [rax], 0
    jz .err_no_token

    ; Copy token to bot_token buffer
    lea rdi, [bot_token]
    mov rsi, rax
    mov rdx, 255
    call strncpy_safe

    lea rdi, [log_token_ok]
    xor eax, eax
    call printf

    ; 2. Initialize libcurl global
    mov rdi, 3              ; CURL_GLOBAL_ALL
    call curl_global_init

    ; 3. Create easy curl handle
    call curl_easy_init
    test rax, rax
    jz .err_curl_init
    mov [curl_handle], rax

    ; 4. Initialize HTTP response buffers
    lea rdi, [resp_buf]
    call buffer_init
    test eax, eax
    jnz .err_mem

    lea rdi, [post_resp_buf]
    call buffer_init
    test eax, eax
    jnz .err_mem

    lea rdi, [log_init_ok]
    xor eax, eax
    call printf

    lea rdi, [log_polling]
    xor eax, eax
    call printf

    ; 5. Main Long-Polling Loop
.polling_loop:
    ; Construct getUpdates URL:
    ; https://api.telegram.org/bot<TOKEN>/getUpdates?offset=<last_offset>&timeout=25
    lea rdi, [req_url]
    mov rsi, 1024
    lea rdx, [fmt_get_updates]
    lea rcx, [bot_token]
    mov r8,  [last_offset]
    xor eax, eax
    call snprintf

    ; Reset response buffer
    lea rdi, [resp_buf]
    call buffer_reset

    ; Execute HTTP GET
    mov rdi, [curl_handle]
    lea rsi, [req_url]
    lea rdx, [resp_buf]
    call http_get

    test rax, rax
    jz .process_response

    ; Network error
    mov rsi, rax
    lea rdi, [log_net_err]
    xor eax, eax
    call printf

    mov rdi, 3
    call sleep
    jmp .polling_loop

.process_response:
    ; Verify that response contains data
    mov rax, [resp_buf + BUF_SIZE]
    test rax, rax
    jz .polling_loop

    ; Process updates in response
    call parse_and_process_updates

    jmp .polling_loop

    ; Cleanup (unreachable in infinite polling loop, but good practice)
    lea rdi, [resp_buf]
    call buffer_free
    lea rdi, [post_resp_buf]
    call buffer_free
    mov rdi, [curl_handle]
    call curl_easy_cleanup
    call curl_global_cleanup

    xor eax, eax
    leave
    ret

.err_no_token:
    lea rdi, [err_token_msg]
    xor eax, eax
    call printf
    mov rdi, 1
    call exit

.err_curl_init:
    mov rdi, 1
    call exit

.err_mem:
    mov rdi, 1
    call exit

; ------------------------------------------------------------------------------
; parse_and_process_updates()
; Scans resp_buf JSON and dispatches incoming messages.
; ------------------------------------------------------------------------------
parse_and_process_updates:
    push rbp
    mov rbp, rsp
    push r12
    push r13
    push r14
    push r15
    push rbx
    sub rsp, 24

    mov r12, [resp_buf + BUF_DATA] ; R12 = JSON pointer
    test r12, r12
    jz .done

    ; Check "ok": true
    mov rdi, r12
    lea rsi, [key_ok]
    call json_find_key
    test rax, rax
    jz .done

    ; Verify value starts with 't' (true)
    cmp byte [rax], 't'
    jne .done

    ; Find "result"
    mov rdi, r12
    lea rsi, [key_result]
    call json_find_key
    test rax, rax
    jz .done
    mov r12, rax            ; R12 = start of result array

.update_loop:
    ; Search for next "update_id"
    mov rdi, r12
    lea rsi, [key_update_id]
    call json_find_key
    test rax, rax
    jz .done                ; No more updates

    mov r13, rax            ; R13 = ptr to update_id value

    ; Parse update_id
    mov rdi, r13
    lea rsi, [temp_update_id]
    call json_parse_int64
    mov r12, rax            ; R12 = pos after update_id

    ; Update offset: if (temp_update_id >= last_offset) last_offset = temp_update_id + 1
    mov rax, [temp_update_id]
    cmp rax, [last_offset]
    jb .find_next_boundary
    inc rax
    mov [last_offset], rax

.find_next_boundary:
    ; Find the next "update_id" position to bound current search
    mov rdi, r12
    lea rsi, [key_update_id]
    call json_find_key
    mov r14, rax            ; R14 = boundary (0 if last update in batch)

    ; Find "chat" in current update
    mov rdi, r12
    lea rsi, [key_chat]
    call json_find_key
    test rax, rax
    jz .next_update

    ; Check boundary
    test r14, r14
    jz .get_chat_id
    cmp rax, r14
    jae .next_update

.get_chat_id:
    ; Find "id" inside "chat"
    mov rdi, rax
    lea rsi, [key_id]
    call json_find_key
    test rax, rax
    jz .next_update

    test r14, r14
    jz .parse_chat_id
    cmp rax, r14
    jae .next_update

.parse_chat_id:
    mov rdi, rax
    lea rsi, [temp_chat_id]
    call json_parse_int64

    ; Find "text"
    mov rdi, r12
    lea rsi, [key_text]
    call json_find_key
    test rax, rax
    jz .next_update

    test r14, r14
    jz .extract_text
    cmp rax, r14
    jae .next_update

.extract_text:
    ; Extract message text into msg_text_buf
    mov rdi, rax
    lea rsi, [msg_text_buf]
    mov rdx, 4096
    call json_parse_string
    test rax, rax
    jz .next_update

    ; Log received update
    lea rdi, [log_update]
    mov rsi, [temp_update_id]
    mov rdx, [temp_chat_id]
    lea rcx, [msg_text_buf]
    xor eax, eax
    call printf

    ; Dispatch command and send response
    mov rdi, [temp_chat_id]
    lea rsi, [msg_text_buf]
    call handle_user_command

.next_update:
    ; If there is a next update boundary, continue from it
    test r14, r14
    jz .done
    mov r12, r14
    jmp .update_loop

.done:
    add rsp, 24
    pop rbx
    pop r15
    pop r14
    pop r13
    pop r12
    leave
    ret

; ------------------------------------------------------------------------------
; handle_user_command(int64_t chat_id, const char *text)
; Analyzes user text and sends formatted HTML reply.
; ------------------------------------------------------------------------------
handle_user_command:
    push rbp
    mov rbp, rsp
    push r12
    push r13
    push r14
    sub rsp, 24

    mov r12, rdi            ; R12 = chat_id
    mov r13, rsi            ; R13 = text

    ; 1. Check /start or /help
    mov rdi, r13
    lea rsi, [cmd_start]
    call cmd_match
    test eax, eax
    jnz .send_welcome

    mov rdi, r13
    lea rsi, [cmd_help]
    call cmd_match
    test eax, eax
    jnz .send_welcome

    ; 2. Check /ping
    mov rdi, r13
    lea rsi, [cmd_ping]
    call cmd_match
    test eax, eax
    jnz .send_ping

    ; 3. Check /calendar or '📲 Календарь'
    mov rdi, r13
    lea rsi, [cmd_calendar]
    call cmd_match
    test eax, eax
    jnz .send_calendar

    mov rdi, r13
    lea rsi, [btn_calendar]
    call strcmp
    test eax, eax
    jz .send_calendar

    ; 4. Check /group or '👥 Курс / Группа'
    mov rdi, r13
    lea rsi, [cmd_group]
    call cmd_match
    test eax, eax
    jnz .send_group

    mov rdi, r13
    lea rsi, [btn_group]
    call strcmp
    test eax, eax
    jz .send_group

    ; 5. Check /week or '🗓 На неделю'
    mov rdi, r13
    lea rsi, [cmd_week]
    call cmd_match
    test eax, eax
    jnz .send_week

    mov rdi, r13
    lea rsi, [btn_week]
    call strcmp
    test eax, eax
    jz .send_week

    ; 6. Check /today or '📅 Сегодня'
    mov rdi, r13
    lea rsi, [cmd_today]
    call cmd_match
    test eax, eax
    jnz .send_today

    mov rdi, r13
    lea rsi, [btn_today]
    call strcmp
    test eax, eax
    jz .send_today

    ; 7. Check /tomorrow or '📆 Завтра'
    mov rdi, r13
    lea rsi, [cmd_tomorrow]
    call cmd_match
    test eax, eax
    jnz .send_tomorrow

    mov rdi, r13
    lea rsi, [btn_tomorrow]
    call strcmp
    test eax, eax
    jz .send_tomorrow

    ; Fallback: Unknown command
    mov rdi, r12
    lea rsi, [msg_unknown]
    call send_telegram_message
    jmp .done

.send_welcome:
    mov rdi, r12
    lea rsi, [msg_welcome]
    call send_telegram_message
    jmp .done

.send_ping:
    mov rdi, r12
    lea rsi, [msg_ping]
    call send_telegram_message
    jmp .done

.send_calendar:
    mov rdi, r12
    lea rsi, [msg_calendar]
    call send_telegram_message
    jmp .done

.send_group:
    mov rdi, r12
    lea rsi, [msg_group_info]
    call send_telegram_message
    jmp .done

.send_week:
    lea rdi, [msg_reply_buf]
    mov rsi, 16384
    call format_week_schedule

    mov rdi, r12
    lea rsi, [msg_reply_buf]
    call send_telegram_message
    jmp .done

.send_today:
    ; Get current date/time via libc time() & localtime()
    xor edi, edi
    call time
    mov [current_time], rax
    lea rdi, [current_time]
    call localtime

    ; Extract struct tm fields:
    ; tm_wday = [rax + 24] (0=Sun, 1=Mon, ..., 6=Sat)
    ; tm_mday = [rax + 12] (1..31)
    ; tm_mon  = [rax + 16] (0..11)
    ; tm_year = [rax + 20] (years since 1900)
    movsxd rdi, dword [rax + 24] ; wday
    movsxd rsi, dword [rax + 12] ; mday
    movsxd rdx, dword [rax + 16] ; mon
    movsxd rcx, dword [rax + 20]
    add rcx, 1900                ; full year
    lea r8, [msg_reply_buf]
    mov r9, 16384
    call format_day_schedule

    mov rdi, r12
    lea rsi, [msg_reply_buf]
    call send_telegram_message
    jmp .done

.send_tomorrow:
    ; Get current time + 86400 seconds (tomorrow)
    xor edi, edi
    call time
    add rax, 86400
    mov [target_time], rax
    lea rdi, [target_time]
    call localtime

    movsxd rdi, dword [rax + 24]
    movsxd rsi, dword [rax + 12]
    movsxd rdx, dword [rax + 16]
    movsxd rcx, dword [rax + 20]
    add rcx, 1900
    lea r8, [msg_reply_buf]
    mov r9, 16384
    call format_day_schedule

    mov rdi, r12
    lea rsi, [msg_reply_buf]
    call send_telegram_message

.done:
    add rsp, 24
    pop r14
    pop r13
    pop r12
    leave
    ret

; ------------------------------------------------------------------------------
; cmd_match(const char *input, const char *cmd)
; Matches command prefix (e.g. "/start", "/start@bot", "/start 123").
; In:  RDI = input
;      RSI = cmd
; Out: RAX = 1 if match, 0 if no match
; ------------------------------------------------------------------------------
cmd_match:
    push rbp
    mov rbp, rsp
    push r12
    push r13
    push rbx
    sub rsp, 8

    mov r12, rdi            ; input
    mov r13, rsi            ; cmd

    ; Get strlen(cmd)
    mov rdi, r13
    call strlen
    mov rbx, rax            ; RBX = cmd_len

    ; strncmp(input, cmd, cmd_len)
    mov rdi, r12
    mov rsi, r13
    mov rdx, rbx
    call strncmp
    test eax, eax
    jnz .no_match

    ; Check char immediately following cmd
    movzx ecx, byte [r12 + rbx]
    test cl, cl
    jz .match
    cmp cl, ' '
    je .match
    cmp cl, '@'
    je .match

.no_match:
    xor eax, eax
    jmp .done

.match:
    mov eax, 1

.done:
    add rsp, 8
    pop rbx
    pop r13
    pop r12
    leave
    ret

; ------------------------------------------------------------------------------
; send_telegram_message(int64_t chat_id, const char *html_text)
; Sends an HTML formatted message with reply keyboard via Telegram Bot API.
; ------------------------------------------------------------------------------
send_telegram_message:
    push rbp
    mov rbp, rsp
    push r12
    push r13
    sub rsp, 16

    mov r12, rdi            ; R12 = chat_id
    mov r13, rsi            ; R13 = html_text

    ; 1. Escape text for JSON inclusion
    mov rdi, r13
    lea rsi, [escaped_text_buf]
    mov rdx, 32768
    call json_escape_string

    ; 2. Format JSON POST payload:
    ; {"chat_id": %ld, "text": "%s", "parse_mode": "HTML", "reply_markup": %s}
    lea rdi, [post_payload]
    mov rsi, 65536
    lea rdx, [fmt_post_json]
    mov rcx, r12
    lea r8,  [escaped_text_buf]
    lea r9,  [keyboard_markup_json]
    xor eax, eax
    call snprintf

    ; 3. Format URL: https://api.telegram.org/bot<TOKEN>/sendMessage
    lea rdi, [send_url]
    mov rsi, 1024
    lea rdx, [fmt_send_msg]
    lea rcx, [bot_token]
    xor eax, eax
    call snprintf

    ; 4. Reset post response buffer
    lea rdi, [post_resp_buf]
    call buffer_reset

    ; 5. Send HTTP POST
    mov rdi, [curl_handle]
    lea rsi, [send_url]
    lea rdx, [post_payload]
    lea rcx, [post_resp_buf]
    call http_post_json

    test rax, rax
    jz .post_ok

    ; POST failed
    mov rsi, rax
    lea rdi, [log_send_err]
    xor eax, eax
    call printf
    jmp .done

.post_ok:
    lea rdi, [log_sent]
    mov rsi, r12
    xor eax, eax
    call printf

.done:
    add rsp, 16
    pop r13
    pop r12
    leave
    ret

; ------------------------------------------------------------------------------
; strncpy_safe(char *dst, const char *src, size_t max_bytes)
; ------------------------------------------------------------------------------
strncpy_safe:
    push rbp
    mov rbp, rsp
    xor ecx, ecx
.loop:
    cmp rcx, rdx
    jae .term
    mov al, [rsi + rcx]
    mov [rdi + rcx], al
    test al, al
    jz .done
    inc rcx
    jmp .loop
.term:
    mov byte [rdi + rdx], 0
.done:
    leave
    ret
