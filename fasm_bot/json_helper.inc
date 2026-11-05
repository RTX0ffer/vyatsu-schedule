; ==============================================================================
; json_helper.inc — Lightweight JSON Parser & Escaper for FASM x86_64 Linux
; ==============================================================================
; Provides key finding, integer parsing, string extraction, and JSON escaping.
; ==============================================================================

section '.text' executable

; ------------------------------------------------------------------------------
; json_skip_ws(const char *p)
; In:  RDI = pointer to string
; Out: RAX = pointer to first non-whitespace character
; ------------------------------------------------------------------------------
json_skip_ws:
    mov rax, rdi
.loop:
    movzx ecx, byte [rax]
    test cl, cl
    jz .done
    cmp cl, ' '
    je .next
    cmp cl, 9       ; tab
    je .next
    cmp cl, 10      ; \n
    je .next
    cmp cl, 13      ; \r
    je .next
    jmp .done
.next:
    inc rax
    jmp .loop
.done:
    ret

; ------------------------------------------------------------------------------
; json_find_key(const char *haystack, const char *key)
; Finds a JSON key `"key":` inside haystack.
; In:  RDI = JSON haystack string
;      RSI = key name without quotes (e.g. "update_id")
; Out: RAX = pointer to the beginning of value after ':', or 0 if not found
; ------------------------------------------------------------------------------
json_find_key:
    push rbp
    mov rbp, rsp
    push r12
    push r13
    push r14
    push r15
    push rbx
    sub rsp, 8              ; align stack

    mov r12, rdi            ; R12 = haystack
    mov r13, rsi            ; R13 = key name

    ; First find length of key
    mov rdi, r13
    call strlen
    mov r14, rax            ; R14 = key_len

.search_loop:
    test r12, r12
    jz .not_found
    cmp byte [r12], 0
    jz .not_found

    ; Search for key substring in current haystack
    mov rdi, r12
    mov rsi, r13
    call strstr
    test rax, rax
    jz .not_found

    mov rbx, rax            ; RBX = match pos

    ; Check if preceded by quote '"'
    cmp rbx, r12
    jbe .advance
    cmp byte [rbx - 1], '"'
    jne .advance

    ; Check if followed by quote '"'
    mov r15, rbx
    add r15, r14            ; R15 = pos after key name
    cmp byte [r15], '"'
    jne .advance

    ; Found '"key"', now skip closing quote
    inc r15

    ; Skip whitespace
    mov rdi, r15
    call json_skip_ws
    mov r15, rax

    ; Must be ':'
    cmp byte [r15], ':'
    jne .advance

    ; Skip ':' and following whitespace
    inc r15
    mov rdi, r15
    call json_skip_ws
    ; RAX now points to start of value!
    jmp .done

.advance:
    ; Key was part of a larger word or didn't have ':', keep searching
    inc rbx
    mov r12, rbx
    jmp .search_loop

.not_found:
    xor eax, eax

.done:
    add rsp, 8
    pop rbx
    pop r15
    pop r14
    pop r13
    pop r12
    leave
    ret

; ------------------------------------------------------------------------------
; json_parse_int64(const char *p, int64_t *out_val)
; In:  RDI = pointer to numeric string
;      RSI = pointer to int64 destination
; Out: RAX = pointer to next character after integer
; ------------------------------------------------------------------------------
json_parse_int64:
    push rbp
    mov rbp, rsp
    push rbx
    push r12
    push r13
    sub rsp, 8

    mov rbx, rdi            ; RBX = p
    mov r12, rsi            ; R12 = out_val

    ; Skip any leading whitespace
    mov rdi, rbx
    call json_skip_ws
    mov rbx, rax

    xor r13d, r13d          ; R13 = negative flag (0 = positive, 1 = negative)
    cmp byte [rbx], '-'
    jne .parse_digits
    mov r13d, 1
    inc rbx

.parse_digits:
    xor rax, rax            ; accumulator

.accum_loop:
    movzx ecx, byte [rbx]
    cmp cl, '0'
    jb .finish_int
    cmp cl, '9'
    ja .finish_int

    sub cl, '0'
    imul rax, 10
    movzx rcx, cl
    add rax, rcx
    inc rbx
    jmp .accum_loop

.finish_int:
    test r13d, r13d
    jz .store
    neg rax

.store:
    mov [r12], rax
    mov rax, rbx            ; Return next position

    add rsp, 8
    pop r13
    pop r12
    pop rbx
    leave
    ret

; ------------------------------------------------------------------------------
; json_parse_string(const char *p, char *out_buf, size_t max_len)
; Parses a quoted JSON string starting at '"' (or skips ws to find '"').
; Unescapes: \" \\ \/ \n \r \t
; In:  RDI = input pointer
;      RSI = output buffer pointer
;      RDX = max output buffer size
; Out: RAX = length of extracted string (excluding null terminator)
; ------------------------------------------------------------------------------
json_parse_string:
    push rbp
    mov rbp, rsp
    push r12
    push r13
    push r14
    push rbx
    sub rsp, 8

    mov r12, rdi            ; R12 = src
    mov r13, rsi            ; R13 = dst
    mov r14, rdx            ; R14 = max_len
    dec r14                 ; leave room for null byte

    ; Skip whitespace
    mov rdi, r12
    call json_skip_ws
    mov r12, rax

    cmp byte [r12], '"'
    jne .empty
    inc r12                 ; skip opening quote

    xor ebx, ebx            ; count written bytes

.copy_loop:
    cmp rbx, r14
    jae .terminate

    movzx ecx, byte [r12]
    test cl, cl
    jz .terminate
    cmp cl, '"'
    je .terminate           ; reached closing quote

    cmp cl, '\'
    jne .regular_char

    ; Escaped character
    inc r12
    movzx ecx, byte [r12]
    test cl, cl
    jz .terminate

    cmp cl, 'n'
    je .esc_newline
    cmp cl, 'r'
    je .esc_cr
    cmp cl, 't'
    je .esc_tab
    cmp cl, '"'
    je .esc_quote
    cmp cl, '\'
    je .esc_slash
    cmp cl, '/'
    je .esc_slash
    ; Fallback for unknown escape: write character as is
    jmp .emit_byte

.esc_newline:
    mov cl, 10
    jmp .emit_byte
.esc_cr:
    mov cl, 13
    jmp .emit_byte
.esc_tab:
    mov cl, 9
    jmp .emit_byte
.esc_quote:
    mov cl, '"'
    jmp .emit_byte
.esc_slash:
    ; CL already has '\' or '/'
    jmp .emit_byte

.regular_char:
.emit_byte:
    mov [r13 + rbx], cl
    inc rbx
    inc r12
    jmp .copy_loop

.empty:
    xor ebx, ebx

.terminate:
    mov byte [r13 + rbx], 0
    mov rax, rbx

    add rsp, 8
    pop rbx
    pop r14
    pop r13
    pop r12
    leave
    ret

; ------------------------------------------------------------------------------
; json_escape_string(const char *src, char *dst, size_t max_dst)
; Escapes text characters: '"' -> '\"', '\' -> '\\', \n -> '\n', \r -> '\r', \t -> '\t'
; In:  RDI = source string (null terminated)
;      RSI = destination buffer
;      RDX = destination capacity
; Out: RAX = length of escaped string
; ------------------------------------------------------------------------------
json_escape_string:
    push rbp
    mov rbp, rsp
    push r12
    push r13
    push r14
    push r15
    push rbx
    sub rsp, 8

    mov r12, rdi            ; R12 = src
    mov r13, rsi            ; R13 = dst
    mov r14, rdx            ; R14 = max_dst
    dec r14                 ; leave room for null terminator
    xor r15, r15            ; R15 = dst index

.loop:
    movzx eax, byte [r12]
    test al, al
    jz .done

    cmp r15, r14
    jae .done

    cmp al, '"'
    je .esc_quote
    cmp al, '\'
    je .esc_backslash
    cmp al, 10              ; \n
    je .esc_newline
    cmp al, 13              ; \r
    je .esc_cr
    cmp al, 9               ; \t
    je .esc_tab

    ; Normal byte
    mov [r13 + r15], al
    inc r15
    inc r12
    jmp .loop

.esc_quote:
    cmp r15, r14
    jae .done
    mov byte [r13 + r15], '\'
    inc r15
    cmp r15, r14
    jae .done
    mov byte [r13 + r15], '"'
    inc r15
    inc r12
    jmp .loop

.esc_backslash:
    cmp r15, r14
    jae .done
    mov byte [r13 + r15], '\'
    inc r15
    cmp r15, r14
    jae .done
    mov byte [r13 + r15], '\'
    inc r15
    inc r12
    jmp .loop

.esc_newline:
    cmp r15, r14
    jae .done
    mov byte [r13 + r15], '\'
    inc r15
    cmp r15, r14
    jae .done
    mov byte [r13 + r15], 'n'
    inc r15
    inc r12
    jmp .loop

.esc_cr:
    cmp r15, r14
    jae .done
    mov byte [r13 + r15], '\'
    inc r15
    cmp r15, r14
    jae .done
    mov byte [r13 + r15], 'r'
    inc r15
    inc r12
    jmp .loop

.esc_tab:
    cmp r15, r14
    jae .done
    mov byte [r13 + r15], '\'
    inc r15
    cmp r15, r14
    jae .done
    mov byte [r13 + r15], 't'
    inc r15
    inc r12
    jmp .loop

.done:
    mov byte [r13 + r15], 0
    mov rax, r15

    add rsp, 8
    pop rbx
    pop r15
    pop r14
    pop r13
    pop r12
    leave
    ret
