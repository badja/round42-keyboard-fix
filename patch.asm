; Constants
LOAD_ADDRESS      equ  100h     ; Address at which COM files are loaded

; Circular buffer for storing keyboard scancodes
struc ScanCodeBuffer
    .buffer      resb  16       ; Array of 16 bytes for storing scancodes
    .head_index  resb   1       ; Index at which scancode was last stored
    .tail_index  resb   1       ; Index at which scancode was last read
    .immediate   resw   1       ; If set, handle buffered scancodes immediately
endstruc

; Variables will be stored after the code (at the vars label)
vars_address  equ  LOAD_ADDRESS + GAME_SIZE + vars

; Variables
buffer      equ  vars_address + ScanCodeBuffer.buffer
head_index  equ  vars_address + ScanCodeBuffer.head_index
tail_index  equ  vars_address + ScanCodeBuffer.tail_index
immediate   equ  vars_address + ScanCodeBuffer.immediate

; Reset the buffer and return a bogus scancode.
; Outputs:
;   AX - bogus scancode (0FFh)
reset_buffer:
    xor ax, ax
    mov [cs:head_index], al     ; Initialise head index to 0
    mov [cs:tail_index], al     ; Initialise tail index to 0
    mov [cs:immediate], al      ; Disable immediate flag
    mov al, 0FFh
    mov [cs:buffer], al         ; Initialise buffer at tail index
    ret

; Add a keyboard scancode to the buffer.
; If the buffer fills up, it is implicitly emptied.
; Inputs:
;   BX - scancode
put_scancode:
    push ax                     ; Backup AX
    mov ax, bx                  ; Copy scancode to AX
    xor bx, bx                  ; Clear BX
    mov bl, [cs:head_index]     ; Load head index
    inc bl                      ; Advance head index
    and bl, 0Fh                 ; Wrap around if necessary
    mov [cs:head_index], bl     ; Update head index
    mov [cs:buffer + bx], al    ; Store scancode at new head index
    cmp [cs:immediate], 0       ; Check immediate flag
    je .done
    call process_scancodes      ; Process all scancodes in buffer immediately
.done:
    pop ax
    ret

; Retrieve the next keyboard scancode from the buffer.
; If the buffer is empty, the last scancode is retrieved.
; Immediate scancode processing is disabled.
; Outputs:
;   AX - scancode
get_scancode:
    push bx                     ; Backup BX
    mov [cs:immediate], al      ; Disable immediate scancode processing
    xor bx, bx                  ; Clear BX
    mov bl, [cs:tail_index]     ; Load tail index
    cmp bl, [cs:head_index]     ; Check if buffer is empty (indexes are equal)
    je .get                     ; Do not move tail index if buffer is empty
    inc bl                      ; Advance tail index
    and bl, 0Fh                 ; Wrap around if necessary
    mov [cs:tail_index], bl     ; Update tail index
.get:
    xor ax, ax                  ; Clear AX
    mov al, [cs:buffer + bx]    ; Get scancode at new tail index
    pop bx                      ; Restore BX
    ret

; Called when a new round is about to start.
; The game stops reading from the buffer while the round number is displayed, so
; process buffered scancodes now and new ones as they arrive until play starts.
on_round_start:
    push ax
    push bx
    call process_scancodes      ; Process all scancodes in buffer
    mov [cs:immediate], 1       ; Enable immediate scancode processing
    mov cx, 8                   ; Run code that was removed by patch process
    pop bx
    pop ax
    ret

; Process scancodes in the buffer until it is empty.
; If a scancode is for an arrow key or F1, let the game's key handler process it
; so it can update movement and bullet flags. Otherwise, ignore the scancode.
process_scancodes:
    xor bx, bx                  ; Clear BX
    mov bl, [cs:tail_index]     ; Load tail index
    cmp bl, [cs:head_index]     ; Check if buffer is empty (indexes are equal)
    je .done                    ; Stop processing if buffer is empty
    inc bl                      ; Advance tail index
    and bl, 0Fh                 ; Wrap around if necessary
    xor ax, ax                  ; Clear AX
    mov al, [cs:buffer + bx]    ; Get scancode at new tail index
    cmp ax, 4Bh                 ; Left make
    je .handle
    cmp ax, 0CBh                ; Left break
    je .handle
    cmp ax, 4Dh                 ; Right make
    je .handle
    cmp ax, 0CDh                ; Right break
    je .handle
    cmp ax, 48h                 ; Up make
    je .handle
    cmp ax, 0C8h                ; Up break
    je .handle
    cmp ax, 50h                 ; Down make
    je .handle
    cmp ax, 0D0h                ; Down break
    je .handle
    cmp ax, 3Bh                 ; F1 make
    je .handle
    cmp ax, 0BBh                ; F1 break
    je .handle
    mov [cs:tail_index], bl     ; Update tail index
    jmp process_scancodes       ; Check for another scancode in buffer
.handle:
    mov bx, GAME_KEY_HANDLER    ; Get address of game's key handler
    call bx                     ; Let game consume scancode and update flags
    jmp process_scancodes       ; Check for another scancode in buffer
.done:
    ret

; Output data (used by patch.py)
vars_size            dw  ScanCodeBuffer_size
addr_reset_buffer    dw  GAME_SIZE + reset_buffer
addr_put_scancode    dw  GAME_SIZE + put_scancode
addr_get_scancode    dw  GAME_SIZE + get_scancode
addr_on_round_start  dw  GAME_SIZE + on_round_start

vars:
