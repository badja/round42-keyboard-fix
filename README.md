# Round 42 Keyboard Fix

This patch fixes the below problems in the DOS game [Round 42](https://www.mobygames.com/game/209/round-42/):

1. The player's ship may move horizontally or vertically instead of diagonally.
2. The player's ship may continue moving after all arrow keys have been released.
3. The player's ship may start moving or fire continuously at the start of a round when no keys are pressed.
4. The player's ship cannot move up when at the leftmost edge of the screen.

## Download

A pre-patched version is available on the [Releases](https://github.com/badja/round42-keyboard-fix/releases) page.

## Causes

The game only stores the last key event in memory. When the game reads the stored key event, if multiple events have occurred since the last time it was read, only the last event is processed. Key events can be missed when:

- Multiple keys are pressed or released simultaneously, e.g. arrow keys
- Multiple key events occur during periods when the game is not reading them, e.g. releasing multiple keys between the end of a round and the start of a new one results in only the last key release being processed.

Some common ways in which these issues manifest are:

- Pressing two adjacent arrow keys simultaneously results in the player's ship moving horizontally or vertically instead of diagonally.
- Releasing both keys when moving diagonally results in the player's ship not stopping but changing to horizontal or vertical movement.
- Holding down two adjacent arrow keys before round ends and releasing them before the start of the next round results in the player's ship moving horizontally or vertically by itself at the start of the round.
- Holding down an arrow key and the fire key before round ends and releasing the fire key then the arrow key before the start of the next round results in the player's ship repeatedly firing by itself at the start of the round.

Although the problem with simultaneous key events may not occur on an original IBM PC, it does occur on other hardware and emulators.

The problem with not being able to move the ship up is simply a software bug where the x-position is being checked instead of the y-position.

## Fix

This patch implements a keyboard buffer to fix the problems.

Although this patch works with both [the original version and version 2.0](https://www.classicdosgames.com/game/Round-42.html), the latter should be avoided because it introduced a bug. In version 2.0, the player cannot proceed past round 13 because all the alien space ships are missing.

## Building a patched version

Requirements:
- [Python](https://www.python.org/) 3.x
- [NASM](https://www.nasm.us/) (must be accessible via the `PATH` environment variable)

Usage:

```
python patch.py input_dir output_dir
```

- `input_dir` is a directory containing `ROUND42.COM`
- `output_dir` is where the patched version will be placed

Example:

```
python patch.py . output
```

This will load `ROUND42.COM` in the current directory and create a patched version at `output/ROUND42.COM`.
