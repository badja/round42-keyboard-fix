# This script assembles patch.asm, appends the result to ROUND42.COM, and makes changes
# to the game code to integrate the patch.
#
# The patch implements a keyboard input buffer to fix missed key events (scancodes).
# Instructions in the game code that read from or write to a 'last_scancode' variable
# are replaced with calls to 'get_scancode' and 'put_scancode' routines in the patch.
# When all of the scancodes have been read from the buffer, subsequent reads return the
# last scancode, as the game expects this. The buffer is large enough (16 bytes) that it
# does not fill up during gameplay, so no overflow handling is implemented.
#
# Before a round starts, the game stops reading from the keyboard buffer while the round
# number message is displayed. To prevent buffer overflow and delayed processing of key
# events during this period, the `on_round_start` routine processes any buffered
# scancodes and enables immediate processing of any new key events until gameplay
# starts. When processing scancodes, the game's original key handler is called to ensure
# the ship movement and bullet firing flags stay in sync with the actual key state.
#
# Also fixed is a bug where the ship cannot move up when at the left edge of the screen.

import subprocess
import struct
import argparse
from pathlib import Path


def patch_version_box(
    game_data: bytearray,
    addr_top: int,
    addr_line1: int,
    addr_line2: int,
    addr_bottom: int,
    line1: str,
    line2: str,
):
    game_data[addr_top : addr_top + 16] = b"\xda" + b"\xc4" * 14 + b"\xbf"
    game_data[addr_line1 : addr_line1 + 16] = f"\xb3{line1:<14}\xb3".encode("ansi")
    game_data[addr_line2 : addr_line2 + 16] = f"\xb3{line2:<14}\xb3".encode("ansi")
    game_data[addr_bottom : addr_bottom + 16] = b"\xc0" + b"\xc4" * 14 + b"\xd9"


def read_le_word(data: bytes, offset: int) -> int:
    return struct.unpack("<H", data[offset : offset + 2])[0]


def write_le_word(data: bytearray, offset: int, value: int):
    struct.pack_into("<H", data, offset, value)


def find_pattern(data: bytes, pattern: bytes) -> int:
    loc = data.find(pattern)
    if loc == -1:
        hex_pattern = " ".join(f"{b:02x}" for b in pattern)
        raise ValueError(f"Could not find pattern: [{hex_pattern}] in input file")
    return loc


def find_pattern_all(data: bytes, pattern: bytes) -> list[int]:
    pos = 0
    results: list[int] = []
    while True:
        pos = data.find(pattern, pos)
        if pos == -1:
            break
        results.append(pos)
        pos += 1
    if not results:
        hex_pattern = " ".join(f"{b:02x}" for b in pattern)
        raise ValueError(f"Could not find pattern: [{hex_pattern}] in input file")
    return results


def patch_call(game_data: bytearray, patch_location: int, size: int, call_address: int):
    offset = call_address - (patch_location + 3)
    patch_bytes = b"\xe8" + struct.pack("<H", offset) + b"\x90" * (size - 3)
    game_data[patch_location : patch_location + size] = patch_bytes


def patch_game(input_dir: Path, output_dir: Path):
    # Constants
    ADDR_LAST_SCANCODE = 0x0F9E  # address that the game uses to store the last scancode
    ADDR_COM_LOAD = 0x100  # address that COM files are loaded at
    DS_LOCATION = 0x2BBF  # location of word in COM file user to set DS register

    # Read game data
    with open(input_dir / "ROUND42.COM", "rb") as f:
        game_data = bytearray(f.read())
    game_size = len(game_data)

    # Create byte patterns to search for
    addr_bytes = struct.pack("<H", ADDR_LAST_SCANCODE)
    pattern_init_scancode = b"\xa3" + addr_bytes  # mov [last_scancode], ax
    pattern_write_scancode = b"\x89\x1e" + addr_bytes  # mov [last_scancode], bx
    pattern_read_scancode = b"\xa1" + addr_bytes  # mov ax, [last_scancode]
    pattern_round_message = b"\xe9\xa7\x01\xb9\x08\x00"  # jmp A7E9; mov cx, 8
    pattern_read_up_flag = b"\xa0\x66\x0c"  # mov al, [C66]
    # Game's key handler begins with: push bp; mov bp, sp; push bp; jmp $
    pattern_key_handler = b"\x55\x8b\xec\x55\xe9\x00\x00" + pattern_read_scancode

    # Find location of game's key handler
    addr_key_handler = find_pattern(game_data, pattern_key_handler) + ADDR_COM_LOAD

    # Create patch.bin
    subprocess.run(
        [
            "nasm",
            f"-dGAME_SIZE={game_size}",
            f"-dGAME_KEY_HANDLER={addr_key_handler}",
            "-f",
            "bin",
            "-o",
            "patch.bin",
            "patch.asm",
        ],
        check=True,
    )

    # Read patch data
    with open("patch.bin", "rb") as f:
        patch_data = f.read()

    # Add/update version box
    if game_size == 0xEC00:
        patch_version_box(
            game_data, 0xE5A2, 0xE5F1, 0xE640, 0xE68F, "Round 42 v1.0", "Keyboard fix 1"
        )
    elif game_size == 0xF382:
        patch_version_box(
            game_data, 0xED21, 0xED44, 0xED93, 0xEDE2, "Round-42 v2.0", "Keyboard fix 1"
        )
    else:
        raise ValueError("Unknown game version")

    # Get patch output data
    vars_size = read_le_word(patch_data, len(patch_data) - 10)
    addr_reset_buffer = read_le_word(patch_data, len(patch_data) - 8)
    addr_put_scancode = read_le_word(patch_data, len(patch_data) - 6)
    addr_get_scancode = read_le_word(patch_data, len(patch_data) - 4)
    addr_on_round_start = read_le_word(patch_data, len(patch_data) - 2)

    # Get and update data segment (DS) value
    end_of_code = ADDR_COM_LOAD + len(game_data) + len(patch_data) + vars_size
    ds_value = read_le_word(game_data, DS_LOCATION)
    data_segment_addr = ds_value * 0x10
    overlap = max(0, end_of_code - data_segment_addr)
    new_ds_value = ds_value + (overlap + 0xF) // 0x10
    write_le_word(game_data, DS_LOCATION, new_ds_value)

    # Replace code with "call reset_buffer"
    loc = find_pattern(game_data, pattern_init_scancode)
    patch_call(game_data, loc, 3, addr_reset_buffer)

    # Replace code with "call put_scancode"
    loc = find_pattern(game_data, pattern_write_scancode)
    patch_call(game_data, loc, 4, addr_put_scancode)

    # Replace code with "call get_scancode"
    for loc in find_pattern_all(game_data, pattern_read_scancode):
        patch_call(game_data, loc, 3, addr_get_scancode)

    # Replace code with "call on_round_start"
    loc = find_pattern(game_data, pattern_round_message) + 3  # after jmp instruction
    patch_call(game_data, loc, 3, addr_on_round_start)

    # Replace xPos with yPos to fix bug where ship cannot move up at left edge of screen
    loc = find_pattern(game_data, pattern_read_up_flag)
    game_data[loc + 7] += 1

    # Write output file
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "ROUND42.COM", "wb") as f:
        f.write(game_data)
        f.write(patch_data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply keyboard fix patch to Round 42")
    parser.add_argument("input_dir", help="Input directory containing ROUND42.COM")
    parser.add_argument("output_dir", help="Output directory for patched game")
    args = parser.parse_args()

    patch_game(Path(args.input_dir), Path(args.output_dir))
