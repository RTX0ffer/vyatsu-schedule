; ==============================================================================
; http_client.inc — Libcurl Wrapper for FASM x86_64 Linux
; ==============================================================================
; Provides memory buffering and HTTP GET / POST JSON requests via libcurl.
; Conforms to System V AMD64 ABI (Linux x86_64).
; ==============================================================================

; --- libcurl Option Constants ---
CURLOPT_URL             equ 10002
CURLOPT_WRITEDATA       equ 10001
CURLOPT_WRITEFUNCTION   equ 20011
CURLOPT_POSTFIELDS      equ 10015
CURLOPT_POSTFIELDSIZE   equ 60
CURLOPT_HTTPHEADER      equ 10023
CURLOPT_TIMEOUT         equ 13
CURLOPT_FOLLOWLOCATION  equ 52
CURLOPT_SSL_VERIFYPEER  equ 64
CURLOPT_HTTPGET         equ 80
CURLOPT_POST            equ 47

; --- Buffer Structure Offsets ---
; struct MemoryBuffer {
;     void   *data;       ; offset 0  (8 bytes)
;     size_t  size;       ; offset 8  (8 bytes)
;     size_t  capacity;   ; offset 16 (8 bytes)
; }
BUF_DATA     equ 0
BUF_SIZE     equ 8
BUF_CAPACITY equ 16
BUF_STRUCT_SIZE equ 24

section '.text' executable

; ------------------------------------------------------------------------------
; buffer_init(Buffer *buf)
; In:  RDI = pointer to Buffer structure
; Out: RAX = 0 on success, -1 on allocation failure
; ------------------------------------------------------------------------------
buffer_init:
    push rbp
    mov rbp, rsp
    push rbx
    sub rsp, 8              ; align stack (16-byte boundary)

    mov rbx, rdi            ; RBX = buf

    mov rdi, 16384          ; initial capacity: 16 KB
    call malloc
    test rax, rax
    jz .fail

    mov [rbx + BUF_DATA], rax
    mov qword [rbx + BUF_SIZE], 0
    mov qword [rbx + BUF_CAPACITY], 16384
    mov byte [rax], 0       ; null-terminate empty buffer

    xor eax, eax
    jmp .done

.fail:
    mov qword [rbx + BUF_DATA], 0
    mov qword [rbx + BUF_SIZE], 0
    mov qword [rbx + BUF_CAPACITY], 0
    mov eax, -1

.done:
    add rsp, 8
    pop rbx
    leave
    ret

; ------------------------------------------------------------------------------
; buffer_reset(Buffer *buf)
; In:  RDI = pointer to Buffer structure
; ------------------------------------------------------------------------------
buffer_reset:
    push rbp
    mov rbp, rsp

    mov qword [rdi + BUF_SIZE], 0
    mov rax, [rdi + BUF_DATA]
    test rax, rax
    jz .done
    mov byte [rax], 0

.done:
    leave
    ret

; ------------------------------------------------------------------------------
; buffer_free(Buffer *buf)
; In:  RDI = pointer to Buffer structure
; ------------------------------------------------------------------------------
buffer_free:
    push rbp
    mov rbp, rsp
    push rbx
    sub rsp, 8

    mov rbx, rdi
    mov rdi, [rbx + BUF_DATA]
    test rdi, rdi
    jz .done
    call free
    mov qword [rbx + BUF_DATA], 0
    mov qword [rbx + BUF_SIZE], 0
    mov qword [rbx + BUF_CAPACITY], 0

.done:
    add rsp, 8
    pop rbx
    leave
    ret

; ------------------------------------------------------------------------------
; curl_write_cb(char *ptr, size_t size, size_t nmemb, Buffer *buf)
; Callback for libcurl CURLOPT_WRITEFUNCTION.
; In:  RDI = incoming bytes pointer
;      RSI = size
;      RDX = nmemb
;      RCX = userdata (Buffer*)
; Out: RAX = total bytes processed (size * nmemb), or 0 on error
; ------------------------------------------------------------------------------
curl_write_cb:
    push rbp
    mov rbp, rsp
    push r12
    push r13
    push r14
    push r15

    ; Total bytes = size * nmemb
    mov rax, rsi
    mul rdx                 ; RDX:RAX = RSI * RDX (fits in RAX)
    mov r12, rax            ; R12 = total_bytes
    mov r13, rdi            ; R13 = ptr (incoming chunk)
    mov r14, rcx            ; R14 = Buffer*

    test r12, r12
    jz .success             ; 0 bytes received is valid

    ; Check if capacity is enough: (size + total_bytes + 1) > capacity
    mov rax, [r14 + BUF_SIZE]
    add rax, r12
    inc rax                 ; +1 for null terminator
    cmp rax, [r14 + BUF_CAPACITY]
    jbe .copy_data

    ; Need reallocation: new_cap = (capacity + total_bytes + 8192) * 2
    mov rax, [r14 + BUF_CAPACITY]
    add rax, r12
    add rax, 8192
    shl rax, 1
    mov r15, rax            ; R15 = new_cap

    mov rdi, [r14 + BUF_DATA]
    mov rsi, r15
    call realloc
    test rax, rax
    jz .error               ; OOM

    mov [r14 + BUF_DATA], rax
    mov [r14 + BUF_CAPACITY], r15

.copy_data:
    ; memcpy(buf->data + buf->size, ptr, total_bytes)
    mov rdi, [r14 + BUF_DATA]
    add rdi, [r14 + BUF_SIZE]
    mov rsi, r13
    mov rdx, r12
    call memcpy

    ; Update size and null-terminate
    mov rax, [r14 + BUF_SIZE]
    add rax, r12
    mov [r14 + BUF_SIZE], rax

    mov rdi, [r14 + BUF_DATA]
    mov byte [rdi + rax], 0

.success:
    mov rax, r12            ; Return processed bytes count
    jmp .done

.error:
    xor eax, eax            ; Return 0 to abort curl transfer

.done:
    pop r15
    pop r14
    pop r13
    pop r12
    leave
    ret

; ------------------------------------------------------------------------------
; http_get(CURL *curl, const char *url, Buffer *buf)
; Executes an HTTP GET request and stores body into buf.
; In:  RDI = curl handle
;      RSI = url
;      RDX = Buffer*
; Out: RAX = CURLE_OK (0) on success, or curl error code
; ------------------------------------------------------------------------------
http_get:
    push rbp
    mov rbp, rsp
    push r12
    push r13
    push r14
    sub rsp, 8              ; 16-byte stack alignment

    mov r12, rdi            ; R12 = curl
    mov r13, rsi            ; R13 = url
    mov r14, rdx            ; R14 = buf

    ; CURLOPT_URL
    mov rdi, r12
    mov rsi, CURLOPT_URL
    mov rdx, r13
    xor eax, eax
    call curl_easy_setopt

    ; CURLOPT_HTTPGET = 1
    mov rdi, r12
    mov rsi, CURLOPT_HTTPGET
    mov rdx, 1
    xor eax, eax
    call curl_easy_setopt

    ; CURLOPT_WRITEFUNCTION = curl_write_cb
    mov rdi, r12
    mov rsi, CURLOPT_WRITEFUNCTION
    lea rdx, [curl_write_cb]
    xor eax, eax
    call curl_easy_setopt

    ; CURLOPT_WRITEDATA = buf
    mov rdi, r12
    mov rsi, CURLOPT_WRITEDATA
    mov rdx, r14
    xor eax, eax
    call curl_easy_setopt

    ; CURLOPT_TIMEOUT = 35 seconds
    mov rdi, r12
    mov rsi, CURLOPT_TIMEOUT
    mov rdx, 35
    xor eax, eax
    call curl_easy_setopt

    ; CURLOPT_FOLLOWLOCATION = 1
    mov rdi, r12
    mov rsi, CURLOPT_FOLLOWLOCATION
    mov rdx, 1
    xor eax, eax
    call curl_easy_setopt

    ; CURLOPT_SSL_VERIFYPEER = 1
    mov rdi, r12
    mov rsi, CURLOPT_SSL_VERIFYPEER
    mov rdx, 1
    xor eax, eax
    call curl_easy_setopt

    ; curl_easy_perform(curl)
    mov rdi, r12
    call curl_easy_perform

    add rsp, 8
    pop r14
    pop r13
    pop r12
    leave
    ret

; ------------------------------------------------------------------------------
; http_post_json(CURL *curl, const char *url, const char *json_body, Buffer *buf)
; Executes an HTTP POST with application/json payload.
; In:  RDI = curl handle
;      RSI = url
;      RDX = json_body
;      RCX = Buffer*
; Out: RAX = CURLE_OK (0) on success, or curl error code
; ------------------------------------------------------------------------------
http_post_json:
    push rbp
    mov rbp, rsp
    push r12
    push r13
    push r14
    push r15
    push rbx
    sub rsp, 24             ; 16-byte stack alignment

    mov r12, rdi            ; R12 = curl
    mov r13, rsi            ; R13 = url
    mov r14, rdx            ; R14 = json_body
    mov r15, rcx            ; R15 = buf

    ; Create header list: "Content-Type: application/json; charset=utf-8"
    xor edi, edi            ; slist = NULL
    lea rsi, [header_content_type]
    call curl_slist_append
    mov rbx, rax            ; RBX = headers slist

    ; CURLOPT_URL
    mov rdi, r12
    mov rsi, CURLOPT_URL
    mov rdx, r13
    xor eax, eax
    call curl_easy_setopt

    ; CURLOPT_POST = 1
    mov rdi, r12
    mov rsi, CURLOPT_POST
    mov rdx, 1
    xor eax, eax
    call curl_easy_setopt

    ; CURLOPT_HTTPHEADER
    mov rdi, r12
    mov rsi, CURLOPT_HTTPHEADER
    mov rdx, rbx
    xor eax, eax
    call curl_easy_setopt

    ; CURLOPT_POSTFIELDS
    mov rdi, r12
    mov rsi, CURLOPT_POSTFIELDS
    mov rdx, r14
    xor eax, eax
    call curl_easy_setopt

    ; Calculate strlen(json_body) for CURLOPT_POSTFIELDSIZE
    mov rdi, r14
    call strlen
    mov rdi, r12
    mov rsi, CURLOPT_POSTFIELDSIZE
    mov rdx, rax
    xor eax, eax
    call curl_easy_setopt

    ; CURLOPT_WRITEFUNCTION = curl_write_cb
    mov rdi, r12
    mov rsi, CURLOPT_WRITEFUNCTION
    lea rdx, [curl_write_cb]
    xor eax, eax
    call curl_easy_setopt

    ; CURLOPT_WRITEDATA = buf
    mov rdi, r12
    mov rsi, CURLOPT_WRITEDATA
    mov rdx, r15
    xor eax, eax
    call curl_easy_setopt

    ; CURLOPT_TIMEOUT = 20 seconds
    mov rdi, r12
    mov rsi, CURLOPT_TIMEOUT
    mov rdx, 20
    xor eax, eax
    call curl_easy_setopt

    ; Execute POST
    mov rdi, r12
    call curl_easy_perform
    mov [rsp], rax          ; Save return status

    ; Free headers slist
    mov rdi, rbx
    call curl_slist_free_all

    mov rax, [rsp]          ; Restore return status
    add rsp, 24
    pop rbx
    pop r15
    pop r14
    pop r13
    pop r12
    leave
    ret

section '.rodata'
header_content_type db 'Content-Type: application/json; charset=utf-8', 0
