#!/usr/bin/env python3
"""The translated machine code of Saloon Cars, and how it's made.

    images.py unpack    the game's own unpackers (tools/unpack: libroger's
                        interpreter running GameCode.LZWD) -> unpacked/: the
                        machine code (CODE), the sound modules, RACE (the
                        BASIC program, behind a stub that copies it to &9000
                        and runs BASIC -quit @9000,1EC3C) -> unpacked/race.bas;
                        OBJECT (squeezed, then BASIC too) -> unpacked/object.bas
    images.py analyse   SuperSpider (analyse --full) on CODE at CODE_ADDRESS,
                        its roots the entry points RACE CALLs (CODE's own
                        offset table) -> analysis/code.json; on LZWD and the
                        sound modules -> analysis/<name>.json
    images.py gen       their C translations -> recomp/gen/<name>/, plus
                        recomp/gen/modules.inc (game.c's module list)
    images.py roots LOG...   gap entries from --trace-gaps runs -> analysis/*.roots

game/!Saloon (libroger's appdir) is the zip's !Saloon, from
$SS/tools/weave.py extract, as recipe.json says (../build.sh).

Either release: Cud's crack of the first (the TOSEC zip: extracted/zip) or
Deluxe (1992, JASPP's three discs: extracted/deluxe1-3, game/!SALOON).
Deluxe isn't compressed but protected (see decrypt_deluxe below): unpack
decrypts its CODE, RACE, OBJECT and voices into unpacked/ instead, and
copies the course disc into !SALOON.DISC2, as its !Install would onto a
hard disc.

Nearly everything is LZW-compressed (LZWD_Decompress, &CD100): GameCode's
CODE, RACE, the cars' icons, the menus, and Sounds' voice modules, which !Run's
Sounds loader decompresses and inserts from memory (OS_Module 11). The game
itself is RACE, a BBC BASIC program (recomp/basic.c, from $SS/tools/bas2c.py);
it LZW-loads CODE into its one DIMmed block and CALLs it.
"""
import hashlib
import os
import shutil
import struct
import subprocess
import sys

TOP = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
SS = os.environ.get('SUPERSPIDER', os.path.expanduser('~/stuff/superspider'))
SSBIN = os.path.join(SS, '_build/default/bin/main.exe')
GAME = os.path.join(TOP, 'game')
EXTRACTED = os.path.join(TOP, 'extracted')
UNP = os.path.join(TOP, 'unpacked')
AN = os.path.join(TOP, 'analysis')
TOOLS = os.path.dirname(os.path.abspath(__file__))

def deluxe():
    """the release weave.py extracted: Deluxe (extracted/deluxe1) or the first"""
    if not os.path.isdir(os.path.join(EXTRACTED, 'deluxe1')):
        return False
    for d in ('deluxe2', 'deluxe3'):
        if not os.path.isdir(os.path.join(EXTRACTED, d)):
            sys.exit('images.py: Deluxe needs all three of its discs (extracted/%s is missing)' % d)
    return True


DELUXE = deluxe()
SALOON = os.path.join(GAME, '!SALOON' if DELUXE else '!Saloon')
CODEDIR = os.path.join(SALOON, 'PROTECT' if DELUXE else 'GameCode')   # CODE, RACE, OBJECT
SOUNDDIR = os.path.join(SALOON, 'PROTECT' if DELUXE else 'Sounds')
CODE = 'code_deluxe' if DELUXE else 'code'      # CODE's analysis (analysis/<CODE>.json, .roots)

# RACE's heap: TOP, then PROC_DIM_ARRAYS's DIM START% MEMSIZE% and its FNRES
# blocks (VAR, ROAD_VAR, PIT_VAR, CARS%, LAPTAB%, RESET%, RSTACK, SKY_SP, GRID%,
# BOIL%, INST%, BUFFER%) before CODE=FNRES(0), which PROC_LOAD_CODE loads CODE
# into. The BASIC runtime's heap (bas_lomem, recomp/game.c) starts at the
# same TOP. The first release's RACE is run by its stub at &9000 (TOP
# &1EC3C); Deluxe's is CHAINed by OBJECT, at BASIC's PAGE, &8F00. Deluxe's
# VAR is bigger (VAR_NEXT), and its CARS% has room for NO_CARS%+1 cars where
# the first's has C_NEXT*NO_CARS%+1 bytes. (Deluxe's DIM of a megabyte
# first, to see whether it has 2MB, is undone by CLEAR.)
PAGE = 0x8F00 if DELUXE else 0x9000
FNRES = [650 if DELUXE else 608, 196, 196, (216 * 31 if DELUXE else 216 * 30 + 1) + 236 + 4 * 32,
         0x100, 168, 0x300, 0xA140, 0x100, 0x40, 0x50, 0x800]


def lomem():
    """TOP (after the program's end marker) rounded to a word"""
    prog = open(os.path.join(UNP, 'race.bas'), 'rb').read()
    return (PAGE + len(prog) + 3) & ~3


def code_address():
    a = lomem()
    for n in FNRES:
        a = (a + n + 3) & ~3
    return a


# the compressed files: (file in !Saloon, unpacked/ name)
CODE_FILES = [('GameCode/CODE', 'code'), ('GameCode/RACE', 'race')]
SOUNDS = ['EN1', 'EN2', 'EN3', 'GEAR', 'SKID', 'SCREAM', 'THUD', 'HORN']   # the Sounds loader's order


def modules():
    """(name, path relative to recomp/, base): LZWD (as !Run RMLoads it), then
    the voices the Sounds loader inserts (Deluxe: !Run2's *<CHR$160>s), each
    in its own 64K of RMA"""
    out = [] if DELUXE else [
        ('lzwd', os.path.relpath(find(CODEDIR, 'LZWD'), os.path.join(TOP, 'recomp')), 0x1840000)]
    for k, s in enumerate(SOUNDS):
        out.append((s.lower(), '../unpacked/' + s.lower(), 0x1850000 + k * 0x10000))
    return out


def find(d, name):
    """a RISC OS file in a host directory: any case, any ,load-exec suffix"""
    for f in os.listdir(d):
        if f.split(',')[0].lower() == name.lower():
            return os.path.join(d, f)
    raise FileNotFoundError(os.path.join(d, name))


def run(cmd, **kw):
    print('+', ' '.join(cmd))
    subprocess.run(cmd, check=True, **kw)


def code_roots():
    """the entry points RACE's PROC_LOAD_CODE reads (FNOFW): CODE + the
    words of the table at CODE - 4 + !CODE"""
    d = open(os.path.join(UNP, 'code'), 'rb').read()
    t = struct.unpack_from('<I', d, 0)[0] - 4
    base = code_address()
    return sorted({base + struct.unpack_from('<I', d, t + 4 * k)[0] for k in range(1, (len(d) - t) // 4)})


# Deluxe's protection, the module ROBIN, is inserted by PROTECT.MECHANIC (an
# absolute that decrypts itself in layers and inserts it from memory, OS_Module
# 11). Its initialisation reads four 256-byte sectors from track 79, side 1
# (ADFS_DiscOp with a disc record of its own: disc address &BCD00), which a
# copy wouldn't have, checks two bytes of them, and claims FileV, ArgsV, BPutV,
# GBPBV, FindV and CLIV: a file loaded while it's there is decrypted, each
# byte XORed with those sectors' (byte k with byte k MOD 1024); saving,
# deleting or *Load, *Save, *Cat, *Drive and the like reset the machine. Its
# command *<CHR$160> loads the next of EN1-HORN (!Run2: at their own address,
# so RMLoaded: Alias$@LoadType_FFA) and then CODE (RACE: *<CHR$160> address);
# RACE *RMKills it after that, before loading anything else. RACE and OBJECT
# (*Run, CHAIN) are loaded through it too. Here those files are decrypted into
# unpacked/ from disc 1's image, which weave.py keeps (recipe.json: "raw"),
# and game.c stands in for MECHANIC, !Run2's *<CHR$160>s, RACE's and the
# *RMKill.
PROTECTED = ['CODE', 'RACE', 'OBJECT'] + SOUNDS
KEY_TRACK = 79 * 2 + 1                          # track 79, side 1: sectors 0-3, 256 bytes each
KEY_SHA = '005f7881d3e02a07c38027ba37decfa1daa4277f421b45d2bd030a3924790325'


def protection_key():
    """the protection sectors, from disc 1's image (extracted/deluxe1.jfd)"""
    sys.path.insert(0, os.path.join(SS, 'tools'))
    import jfd
    p = os.path.join(EXTRACTED, 'deluxe1.jfd')
    if not os.path.exists(p):
        sys.exit('images.py: Deluxe needs disc 1\'s image as JASPP made it (extracted/deluxe1.jfd)')
    secs = jfd.tracks(jfd.load(p))[KEY_TRACK] or []
    key = b''.join(d for r, n, ok, d in sorted(secs) if r < 4 and n == 1 and d)
    if hashlib.sha256(key).hexdigest() != KEY_SHA:
        sys.exit('images.py: %s: the protection sectors (track 79, side 1) aren\'t the ones expected' % p)
    return key


def unpack_deluxe():
    key = protection_key()
    for name in PROTECTED:
        d = open(find(CODEDIR, name), 'rb').read()
        d = bytes(c ^ key[k & 1023] for k, c in enumerate(d))
        out = name.lower()
        if name in ('RACE', 'OBJECT'):
            if d[:1] != b'\r':
                sys.exit('images.py: %s isn\'t BASIC once decrypted' % name)
            d, out = d[:d.index(b'\r\xff') + 2], out + '.bas'
        print('  decrypting %s -> unpacked/%s' % (name, out))
        open(os.path.join(UNP, out), 'wb').write(d)
    # the course disc, as !Install puts it on a hard disc: SALOON3$DIR,
    # <SALOON$DIR>.DISC2, is where RACE looks for it before asking for it
    disc2 = os.path.join(SALOON, 'DISC2')
    shutil.rmtree(disc2, ignore_errors=True)
    shutil.copytree(os.path.join(EXTRACTED, 'deluxe3'), disc2)
    print('CODE at &%X; RACE %d bytes, TOP &%X' % (code_address(), len(open(os.path.join(UNP, 'race.bas'), 'rb').read()),
                                                  lomem()))


# --- unpack, analyse, gen, roots
def unpack():
    os.makedirs(UNP, exist_ok=True)
    for f in os.listdir(UNP):                   # (from the other release's build)
        os.remove(os.path.join(UNP, f))
    if DELUXE:
        return unpack_deluxe()
    run(['make', '-C', TOOLS, 'unpack'])
    pairs = ['%s=%s' % (find(os.path.join(SALOON, os.path.dirname(f)), os.path.basename(f)), os.path.join(UNP, n))
             for f, n in CODE_FILES]
    pairs += ['%s=%s' % (find(SOUNDDIR, s), os.path.join(UNP, s.lower())) for s in SOUNDS]
    run([os.path.join(TOOLS, 'unpack'), '--out=' + os.path.join(UNP, 'unpack'),
         '--lzwd=' + find(CODEDIR, 'LZWD')] + pairs)
    # RACE: a stub (copy the program to &9000, *BASIC -quit @9000,1EC3C) and
    # the tokenised program after it, its length the stub's first literal
    race = open(os.path.join(UNP, 'race'), 'rb').read()
    n = struct.unpack_from('<I', race, 0x48)[0]
    assert race[0x24:0x39] == b'BASIC -quit @00009000', race[0x24:0x48]
    prog = race[0x54:0x54 + n]
    end = prog.index(b'\r\xff') + 2                      # TOP: after the end marker
    open(os.path.join(UNP, 'race.bas'), 'wb').write(prog[:end])
    assert lomem() == 0x1EC3C, hex(lomem())
    # OBJECT, the program !Run RUNs: Acorn-squeezed (its stub ends with mov
    # pc, r8 into the image at &8000), then a stub like RACE's around
    # another BASIC program, which game.c follows (its DATA: the pointers)
    obj = os.path.join(UNP, 'object')
    run([os.path.join(TOOLS, 'unpack'), find(CODEDIR, 'OBJECT'), '--stop=8000',
         '--dump=8000:10000', '--write=' + obj, '--out=' + os.path.join(UNP, 'unpack')])
    o = open(obj, 'rb').read()
    n = struct.unpack_from('<I', o, 0x48)[0]
    assert o[0x24:0x39] == b'BASIC -quit @00009000', o[0x24:0x48]
    prog = o[0x54:0x54 + n]
    open(os.path.join(UNP, 'object.bas'), 'wb').write(prog[:prog.index(b'\r\xff') + 2])
    print('CODE at &%X; RACE %d bytes, TOP &%X' % (code_address(), end, 0x9000 + end))


def analyse():
    os.makedirs(AN, exist_ok=True)
    roots = os.path.join(AN, CODE + '.roots')
    calls = os.path.join(AN, 'calls.roots')
    with open(calls, 'w') as f:
        f.write('# the entry points RACE CALLs (CODE\'s table: images.py code_roots)\n')
        f.writelines('%x\n' % a for a in code_roots())
    if not os.path.exists(roots):
        open(roots, 'w').write('# gap entries from --trace-gaps runs (images.py roots)\n')
    merged = os.path.join(AN, 'all.roots')
    open(merged, 'w').write(open(calls).read() + open(roots).read())
    run(['dune', 'build'], cwd=SS)
    run([SSBIN, 'analyse', os.path.join(UNP, 'code'), '%x' % code_address(), '--full', '--roots', merged,
         '-o', os.path.join(AN, CODE + '.json')])
    rc = os.path.join(TOP, 'recomp')
    for name, path, base in modules():
        rf = os.path.join(AN, name + '.roots')
        run([SSBIN, 'analyse', os.path.join(rc, path), '%x' % base, '--module', '--full',
             '-o', os.path.join(AN, name + '.json')] + (['--roots', rf] if os.path.exists(rf) else []))


def gen():
    rc = os.path.join(TOP, 'recomp')
    shutil.rmtree(os.path.join(rc, 'gen'), ignore_errors=True)
    run([SSBIN, 'gen', os.path.join(UNP, 'code'), '%x' % code_address(), os.path.join(AN, CODE + '.json'),
         '--c', os.path.join(rc, 'gen', 'code')])
    for k, (name, path, base) in enumerate(modules()):
        run([SSBIN, 'gen', os.path.join(rc, path), '%x' % base, os.path.join(AN, name + '.json'),
             '--c', os.path.join(rc, 'gen', name), '--prefix', 'M%d' % k, '--tabprefix', 'recomp_' + name,
             '--files', '1', '--covtag', chr(ord('a') + k)])
    with open(os.path.join(rc, 'gen', 'modules.inc'), 'w') as f:
        f.write('/* generated by ../tools/images.py - the modules, for game.c */\n')
        for name, _, _ in modules():
            f.write('extern const struct roger_image recomp_%s_image;\n' % name)
        f.write('static const struct roger_module modules[] = {\n')
        for name, path, _ in modules():
            f.write('    {"%s", &recomp_%s_image, 0},\n' % (path, name))
        f.write('    {NULL, NULL, 0}};\n')
        f.write('#define CODE_ADDRESS 0x%X\n' % code_address())
        f.write('#define BAS_PAGE 0x%X                 /* where RACE runs, and its TOP */\n' % PAGE)
        f.write('#define BAS_LOMEM 0x%X\n' % lomem())
        f.write('#define DELUXE %d                      /* Saloon Cars Deluxe (1992) */\n' % DELUXE)
        if DELUXE:
            f.write('#define CODE_LENGTH %d\n' % os.path.getsize(os.path.join(UNP, 'code')))


def roots(logs):
    rc = os.path.join(TOP, 'recomp')
    run([sys.executable, os.path.join(SS, 'tools/gap_roots.py'), os.path.join(UNP, 'code'), '%x' % code_address(),
         os.path.join(AN, CODE + '.roots')] + logs)
    for name, path, base in modules():
        run([sys.executable, os.path.join(SS, 'tools/gap_roots.py'), os.path.join(rc, path), '%x' % base,
             os.path.join(AN, name + '.roots')] + logs)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if sys.argv[1] == 'roots':
        roots(sys.argv[2:])
    else:
        for step in sys.argv[1:]:
            {'unpack': unpack, 'analyse': analyse, 'gen': gen}[step]()
