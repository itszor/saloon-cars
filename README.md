Saloon Cars (Andy Swain / The Fourth Dimension, 1991) - static recompilation
==========================================================================

A recipe: this repository holds no game data. It rebuilds the game as a
native executable from your own copy, recognised by content (recipe.json),
so it can be shared without distributing the game.

    ./build.sh "Saloon Cars ()(Fourth Dimension).zip"     (or a directory holding !Saloon)
    cd recomp && ./salooncars

build.sh runs recipe.json's steps with SuperSpider's tools/weave.py
(~/stuff/superspider, or $SUPERSPIDER; $SS below): it extracts the zip,
runs the game's own decompressor to unpack the code, analyses and
translates it, translates the BASIC, and links it all with libroger
(~/stuff/libroger, or make ROGER=...). It takes about a minute. Needs
python3, OCaml/dune, gcc and SDL3.

The input is the TOSEC zip, `Saloon Cars ()(Fourth Dimension).zip`: a
SparkFS zip of !Saloon with RISC OS filetypes, most members "imploded"
(PKWARE's method 6, which $SS/tools/implode.py reads). It is Cud's July
1991 crack ("Hacked By Cud"), both discs in one application (Disc2 is the
course disc's contents).

    extracted/zip            the zip's !Saloon, via weave.py
    game/!Saloon             a copy: libroger's appdir (../game)
    unpacked/                tools/images.py unpack: CODE, the voice modules,
                             race.bas and object.bas (the tokenised BASIC)
    analysis/*.json          SuperSpider's analyses (CODE, LZWD, the voices)
    recomp/gen/              their C translations; recomp/basic.c RACE's
    recomp/salooncars        the game
    basic/                   make -C recomp basic: RACE and OBJECT as text, to read

Committed: recipe.json, build.sh, tools/images.py, tools/unpack.c,
tools/Makefile, recomp/ (Makefile, game.c),
analysis/code.roots (when there are any), this file.

How the game is put together
----------------------------

Nearly every file is LZW-compressed and read through Cud's LZWD module
(LZWD_Decompress, &CD100). !Run RMLoads it, sets 160K of screen (two mode
13 banks), and runs:

- SCREENLOAD (BASIC): decompresses GameCode.SALOON, the title picture, into
  the second bank and shows it.
- Sounds.Sounds (BASIC): decompresses the eight voice modules (EN1-3, GEAR,
  SKID, SCREAM, THUD, HORN) and inserts them from memory (OS_Module 11).
- *PRINT RACECHAR: the character set.
- OBJECT: Acorn-squeezed, then a stub that copies the BASIC program inside it
  to &9000 and runs `BASIC -quit @9000,...`: the two mouse pointers. It
  *LOADs CUD at &7F00 and *GOes it; CUD decompresses RACE to &8000 and jumps
  there: another such stub, around RACE, the game.

RACE (BBC BASIC, 4,300 lines) is the front end - menus, players, cars,
courses, money, the garage - and LZW-loads CODE (the machine code: the
race, the screen effects, the course map) into its one DIMmed block, at
an address that depends only on the program's size (&2BA5C), and CALLs
it through CODE's own table of entry points.

- tools/unpack.c runs the game's own unpackers under libroger's ARM2
  interpreter: LZWD_Decompress for CODE, RACE and the voices, and OBJECT's
  squeeze stub. tools/images.py takes the BASIC programs out of their
  stubs.
- recomp/basic.c: RACE, translated by $SS/tools/bas2c.py, on SuperSpider's
  BASIC runtime ($SS/runtime/basic_runtime.c), its heap (bas_lomem, in
  game.c) at RACE's TOP, &1EC3C. RACE
  GOTOs into the middle of other PROCs, lets PROCs run on into the next DEF,
  and sets ON ERROR handlers inside PROCs that GOTO the main program;
  bas2c handles all three (see its docstring).
- recomp/game.c: !Run, SCREENLOAD and OBJECT by hand (OBJECT's pointer
  shapes are read from its DATA in unpacked/object.bas), then RACE.
- CODE, LZWD and the voices are translated; the voices are loaded up front
  (gen/modules.inc). Everything translates: a headless run through the
  menus and a demo race, or a practice drive and crash (4e8 instructions),
  interprets only the words CODE modifies as it runs (7,000-11,000
  instructions). analysis/code.roots holds the gap entries --trace-gaps
  found (make roots): the branches of an `add pc, pc, r0, lsr #4` on a byte
  (SuperSpider doesn't know a byte load's range), and one after a branch
  CODE rewrites.

The screen shake
----------------

The race claims EventV, and its vsync handler (CODE &33AB8) runs two damped
springs every frame - one vertical, kicked by bumps and the suspension, one
horizontal, kicked by crashes - and writes the results straight into
VIDC's timing registers: VDSR/VDER (where the picture starts and ends,
vertically) and HDSR/HDER (horizontally). The picture moves within the
monitor's window, leaving border at one edge.

libroger shows VIDC's horizontal display start and end as the hardware
would, and now its vertical ones too: a VDSR later than the standard mode's
moves the picture down, an earlier one up (its first lines are fetched
above the window). At rest the game sets HDSR to 64, where RISC OS's mode
13 has 63, so in a race the picture sits 2 pixels right of the desktop's,
with 2 columns of border at the left; that is what VIDC does with that
value, and is left as it is.

Fonts
-----

The menus are painted with Font_Paint in Trinity.Medium at 30 point,
anti-aliased, from the font on the course disc (Disc2.FONTS: RISC OS 2's
pixel font format, an IntMetrics and an x90y45 file). libroger has a Font
Manager for these now: it scales the nearest bitmap size to the size and
resolution asked for and paints each level in the screen's closest colour
(Font_SetPalette's colours in 256-colour modes).

Controls
--------

Menus: the mouse, or the number keys. Driving, with the mouse (the
default): steer by moving it left and right, right button accelerate,
middle brake, left kickdown. S (held) starts the engine, D drive, R
reverse, N neutral, H the handbrake; Q with F12 leaves the car. The
keyboard controls (Control Menu): Z/X steer, Page Down accelerate, Copy
(End) brake, Delete kickdown, up/down arrows change gear. A game controller
drives the keyboard controls: stick or D-pad left/right steer, A
accelerate, B brake, X kickdown, Y handbrake, LB start engine, RB drive,
LT reverse, RT neutral.

The race moves by the number of vsyncs since its last frame (at most 3),
so it keeps time at any speed, but its engine sound doesn't: once a frame
it sets the engine's amplitude and pitch as a new note, which restarts the
engine voice's sample. On an 8MHz ARM2 a race frame (~200,000
instructions) comes about 20 times a second; unthrottled it would be every
vsync, and the engine only a 50Hz buzz. So game.c sets libroger's CPU speed
to an ARM2's, 4.5 MIPS (--mips=N to change it, 0 for flat out). The
engine is silent when switched off: the game sends it BBC amplitude 0, which
libroger now takes as silence.

A headless scenario (Race Menu, Solo Practice, start the engine, drive,
handbrake off, accelerate and run off the track at the first bend -
screenshots as screenshot-N.bmp):

    ./salooncars --limit=1.2e8 --full-os --script=9000:click:640:592,9300:release,\
    10500:type:49,14000:key:82:3000,19000:key:51:1500,21000:key:85:800,\
    22500:buttons:1,26000:shot,33600:shot,33800:shot,34000:shot

Not done
--------

- The two-player game over a serial link (OS_SerialOp, RS423).
- The RTFM/analogue joystick interfaces (IO_TEST probes podule space at
  &33A0000, which reads as nothing).
- Saving players and lap times goes to recomp/savedata (libroger's save
  directory), not tried in depth.
