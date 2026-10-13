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

Nearly everything is LZW-compressed (LZWD_Decompress, &CD100): GameCode's
CODE, RACE, the cars' icons, the menus, and Sounds' voice modules, which !Run's
Sounds loader decompresses and inserts from memory (OS_Module 11). The game
itself is RACE, a BBC BASIC program (recomp/basic.c, from $SS/tools/bas2c.py);
it LZW-loads CODE into its one DIMmed block and CALLs it.
"""
import os
import shutil
import struct
import subprocess
import sys

TOP = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
SS = os.environ.get('SUPERSPIDER', os.path.expanduser('~/stuff/superspider'))
SSBIN = os.path.join(SS, '_build/default/bin/main.exe')
GAME = os.path.join(TOP, 'game')
SALOON = os.path.join(GAME, '!Saloon')
UNP = os.path.join(TOP, 'unpacked')
AN = os.path.join(TOP, 'analysis')
TOOLS = os.path.dirname(os.path.abspath(__file__))

# RACE's heap: TOP (&1EC3C), then PROC_DIM_ARRAYS's DIM START% MEMSIZE% and its
# FNRES blocks (VAR, ROAD_VAR, PIT_VAR, CARS%, LAPTAB%, RESET%, RSTACK, SKY_SP,
# GRID%, BOIL%, INST%, BUFFER%) before CODE=FNRES(0), which PROC_LOAD_CODE
# decompresses CODE into. recomp/bas.c's heap starts at the same TOP.
LOMEM = 0x1EC3C
FNRES = [608, 196, 196, 216 * 30 + 1 + 236 + 4 * 32, 0x100, 168, 0x300, 0xA140, 0x100, 0x40, 0x50, 0x800]


def code_address():
    a = LOMEM
    for n in FNRES:
        a = (a + n + 3) & ~3
    return a


# the compressed files: (file in !Saloon, unpacked/ name)
CODE_FILES = [('GameCode/CODE', 'code'), ('GameCode/RACE', 'race')]
SOUNDS = ['EN1', 'EN2', 'EN3', 'GEAR', 'SKID', 'SCREAM', 'THUD', 'HORN']   # the Sounds loader's order


def modules():
    """(name, path relative to recomp/, base): LZWD (as !Run RMLoads it), then
    the voices the Sounds loader inserts, each in its own 64K of RMA"""
    out = [('lzwd', os.path.relpath(find(os.path.join(SALOON, 'GameCode'), 'LZWD'), os.path.join(TOP, 'recomp')),
            0x1840000)]
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


# --- unpack, analyse, gen, roots
def unpack():
    os.makedirs(UNP, exist_ok=True)
    run(['make', '-C', TOOLS, 'unpack'])
    pairs = ['%s=%s' % (find(os.path.join(SALOON, os.path.dirname(f)), os.path.basename(f)), os.path.join(UNP, n))
             for f, n in CODE_FILES]
    pairs += ['%s=%s' % (find(os.path.join(SALOON, 'Sounds'), s), os.path.join(UNP, s.lower())) for s in SOUNDS]
    run([os.path.join(TOOLS, 'unpack'), '--out=' + os.path.join(UNP, 'unpack'),
         '--lzwd=' + find(os.path.join(SALOON, 'GameCode'), 'LZWD')] + pairs)
    # RACE: a stub (copy the program to &9000, *BASIC -quit @9000,1EC3C) and
    # the tokenised program after it, its length the stub's first literal
    race = open(os.path.join(UNP, 'race'), 'rb').read()
    n = struct.unpack_from('<I', race, 0x48)[0]
    assert race[0x24:0x39] == b'BASIC -quit @00009000', race[0x24:0x48]
    prog = race[0x54:0x54 + n]
    end = prog.index(b'\r\xff') + 2                      # TOP: after the end marker
    assert (0x9000 + end + 3) & ~3 == LOMEM, hex(0x9000 + end)
    open(os.path.join(UNP, 'race.bas'), 'wb').write(prog[:end])
    # OBJECT, the program !Run RUNs: Acorn-squeezed (its stub ends with mov
    # pc, r8 into the image at &8000), then a stub like RACE's around
    # another BASIC program, which game.c follows (its DATA: the pointers)
    obj = os.path.join(UNP, 'object')
    run([os.path.join(TOOLS, 'unpack'), find(os.path.join(SALOON, 'GameCode'), 'OBJECT'), '--stop=8000',
         '--dump=8000:10000', '--write=' + obj, '--out=' + os.path.join(UNP, 'unpack')])
    o = open(obj, 'rb').read()
    n = struct.unpack_from('<I', o, 0x48)[0]
    assert o[0x24:0x39] == b'BASIC -quit @00009000', o[0x24:0x48]
    prog = o[0x54:0x54 + n]
    open(os.path.join(UNP, 'object.bas'), 'wb').write(prog[:prog.index(b'\r\xff') + 2])
    print('CODE at &%X; RACE %d bytes, TOP &%X' % (code_address(), end, 0x9000 + end))


def analyse():
    os.makedirs(AN, exist_ok=True)
    roots = os.path.join(AN, 'code.roots')
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
         '-o', os.path.join(AN, 'code.json')])
    rc = os.path.join(TOP, 'recomp')
    for name, path, base in modules():
        rf = os.path.join(AN, name + '.roots')
        run([SSBIN, 'analyse', os.path.join(rc, path), '%x' % base, '--module', '--full',
             '-o', os.path.join(AN, name + '.json')] + (['--roots', rf] if os.path.exists(rf) else []))


def gen():
    rc = os.path.join(TOP, 'recomp')
    shutil.rmtree(os.path.join(rc, 'gen'), ignore_errors=True)
    run([SSBIN, 'gen', os.path.join(UNP, 'code'), '%x' % code_address(), os.path.join(AN, 'code.json'),
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


def roots(logs):
    rc = os.path.join(TOP, 'recomp')
    run([sys.executable, os.path.join(SS, 'tools/gap_roots.py'), os.path.join(UNP, 'code'), '%x' % code_address(),
         os.path.join(AN, 'code.roots')] + logs)
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
