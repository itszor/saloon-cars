/* Saloon Cars (Andy Swain / The Fourth Dimension, 1991): what libroger
 * needs to know about the game.
 *
 * !Run (the TOSEC copy is Cud's July 1991 crack, everything LZW-compressed
 * and loaded through his LZWD module): sets SALOON$DIR..SALOON4$DIR,
 * RMLoads LZWD, 160K of screen (two mode 13 banks), WimpSlot 600K; BASIC
 * SCREENLOAD decompresses the title picture (GameCode.SALOON) into bank 2,
 * which is then shown; Sounds.Sounds (BASIC) decompresses the eight voice
 * modules and inserts them; *PRINT RACECHAR defines the character set; and
 * it RUNs OBJECT, a squeezed BASIC program (the two mouse pointers), which
 * *LOADs CUD at &7F00 and *GOes it: CUD decompresses RACE to &8000 and
 * jumps there, a stub that runs the BASIC program inside it - the game
 * (basic.c, translated by SuperSpider's tools/bas2c.py). RACE LZW-loads the
 * machine code (CODE) into its DIMmed block and CALLs it.
 *
 * Here: the modules are loaded up front (LZWD and the voices, unpacked by
 * ../tools/images.py), setup() does SCREENLOAD, RACECHAR and OBJECT, and
 * bas_main() is RACE.
 *
 * Or Saloon Cars Deluxe (1992: DELUXE, from gen/modules.inc - the release
 * ../tools/images.py found), from JASPP's discs: nothing compressed, but
 * CODE, RACE, OBJECT and the voices encrypted, and loaded through the
 * protection's module, ROBIN, which PROTECT.MECHANIC inserts (see
 * images.py). !Run: SALOON$DIR..SALOON3$DIR, SETMODE (160K of screen),
 * WimpSlot 630K-1500K; !Run2: MECHANIC, *PRINT RACECHAR, eight *<CHR$160>s
 * (ROBIN's command: RMLoad the next voice), mode 13, and RUN OBJECT, which
 * CHAINs RACE. RACE loads CODE with *<CHR$160> address and *RMKills ROBIN.
 * Here images.py has decrypted them: the voices are loaded up front,
 * deluxe_cli() stands in for RACE's *<CHR$160> and *RMKill ROBIN, and the
 * course disc is in !SALOON.DISC2, where RACE looks for it first (as
 * !Install would put it on a hard disc). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "basic_runtime.h"

/* CODE's translation (make regen), at the address RACE's PROC_LOAD_CODE
 * decompresses it to (CODE_ADDRESS, ../tools/images.py). It's loaded up
 * front; the BASIC's LZWD_Decompress then writes the same bytes over it,
 * which leaves the translation in place. */
extern const struct roger_image recomp_image;

#include "gen/modules.inc"      /* LZWD and the voice modules; CODE_ADDRESS */

/* the BASIC runtime ($SS/runtime/basic_runtime.c): PAGE (RACE's wrapper runs
 * BASIC -quit @9000,1EC3C; Deluxe's OBJECT CHAINs it, at &8F00) and the heap
 * above the program (TOP: BAS_LOMEM, &1EC3C).
 * The game's memory is the block DIM START% MEMSIZE%; CODE is LZW-loaded
 * into it at an address that depends only on the DIMs before it
 * (CODE_ADDRESS). DIM doesn't clear its blocks (BASIC doesn't): CODE's
 * translation is in this memory, loaded up front, and the LZWD_Decompress
 * that loads CODE again must find the words it was translated from there,
 * not zeros, or every word of it would count as self-modified */
int32_t bas_page = BAS_PAGE;
uint32_t bas_lomem = BAS_LOMEM;

#if DELUXE
static const char *const vars[] = {
    "SALOON$DIR", "!SALOON",
    "SALOON2$DIR", "!SALOON.PROTECT",
    "SALOON3$DIR", "!SALOON.DISC2",
    "Disc1$Dir", "!SALOON.PROTECT.",
    NULL};
#else
static const char *const vars[] = {
    "SALOON$DIR", "!Saloon",
    "SALOON2$DIR", "!Saloon.GameCode",
    "SALOON3$DIR", "!Saloon.Disc2",
    "SALOON4$DIR", "!Saloon.Sounds",
    NULL};
#endif
static const char *const prefixes[] = {"<SALOON$DIR>.", NULL};

/* OBJECT's DATA statements, read from its program (../unpacked/object.bas,
 * tokenised: a line is CR, the line number (2 bytes), its length, then its
 * tokens; DATA is &DC, followed by the items as text) */
static char *odata[200];
static int nodata, op;

static void read_object(void)
{
    static uint8_t prog[8192];
    FILE *f = fopen("../unpacked/object.bas", "rb");
    if (!f) { perror("../unpacked/object.bas"); exit(1); }
    size_t n = fread(prog, 1, sizeof prog, f);
    fclose(f);
    for (size_t p = 0; p + 4 <= n && prog[p] == 13 && prog[p + 1] != 0xFF; p += prog[p + 3]) {
        size_t q = p + 4, end = p + prog[p + 3];
        while (q < end && prog[q] == ' ') q++;
        if (q >= end || prog[q] != 0xDC) continue;
        char line[256];
        size_t l = 0;
        for (q++; q < end && prog[q] != 13 && l < sizeof line - 1; q++) line[l++] = (char)prog[q];
        line[l] = 0;
        for (char *s = strtok(line, ","); s && nodata < 200; s = strtok(NULL, ",")) {
            while (*s == ' ') s++;
            odata[nodata++] = strdup(s);
        }
    }
}

static const char *oread(void)
{
    if (op >= nodata) { fprintf(stderr, "OBJECT: out of DATA\n"); exit(1); }
    return odata[op++];
}

/* OBJECT (BASIC, by hand): the sound system, and the two pointers - shapes
 * 2 and 3, 32x32 in its DATA ('.' '/' '0' '1' colours 0-3, '*' the active
 * point) with their colours */
static void object(void)
{
    oscli_c("FX 13,4");
    R[0] = 2; R[1] = R[2] = R[3] = R[4] = 0;
    roger_swi(0x40140);                          /* Sound_Configure 2 */
    sound(1, 0, 0x1000, 0xFF);
    read_object();
    const uint32_t dat = 0x8100, block = 0x8300; /* (free: below RACE's PAGE, &9000) */
    for (int i = 0; i < 2; i++) {
        int num = atoi(oread());
        const char *a = oread();
        int xpos = (int)(strchr(a, '*') ? strchr(a, '*') - a + 1 : 0), ypos = 0;
        for (int x = 0; x < 32; x++) {
            a = oread();
            for (int y = 0; y < 8; y++) {
                int q = 0;
                for (int z = 0; z < 8; z += 2) q += (a[y * 4 + z / 2] - 46) << z;
                PB(dat + x * 8 + y) = (uint8_t)q;
            }
            if (a[strlen(a) - 1] == '*') ypos = x;
        }
        PB(block) = 0; PB(block + 1) = (uint8_t)num; PB(block + 2) = 8; PB(block + 3) = 0x20;
        PB(block + 4) = (uint8_t)xpos; PB(block + 5) = (uint8_t)ypos;
        for (int k = 0; k < 4; k++) PB(block + 6 + k) = (uint8_t)(dat >> (8 * k));
        R[0] = 0x15; R[1] = block;
        roger_swi(0x07);                         /* OS_Word 21,0: define the pointer */
        for (int c = 1; c <= 3; c++) {           /* MOUSE COLOUR c, r, g, b */
            int r = atoi(oread()), g = atoi(oread()), b = atoi(oread());
            vdu(19, c, 25, r, g, b, -1);
        }
    }
    R[0] = 106; R[1] = 3; roger_swi(0x06);       /* MOUSE ON 3 */
}

#if DELUXE
/* ROBIN's command, as RACE's PROC_LOAD_CODE uses it: *<CHR$160> address
 * loads (and decrypts) CODE there; its first eight, !Run2's, RMLoaded the
 * voices, which are loaded already. RACE then *RMKills it */
static int deluxe_cli(const char *c)
{
    while (*c == ' ' || *c == '*') c++;
    if (!strcasecmp(c, "RMKILL ROBIN")) return 1;
    if ((uint8_t)c[0] != 0xA0) return 0;
    uint32_t a = (uint32_t)strtoul(c + 1, NULL, 16);
    FILE *f = fopen("../unpacked/code", "rb");
    if (!f || !a || fread(&PB(a), 1, CODE_LENGTH, f) != CODE_LENGTH) {
        perror("../unpacked/code");
        exit(1);
    }
    fclose(f);
    return 1;
}

/* !Run and !Run2's steps before OBJECT: SETMODE's 160K of screen is the
 * config's; MECHANIC and the *<CHR$160>s insert the voices, loaded already */
static void setup(void)
{
    bas_cli = deluxe_cli;
    mode(13);                                    /* ECHO <22><&8D> */
    oscli_c("PRINT <SALOON2$DIR>.RACECHAR");
    mode(13);
    oscli_c("FX 112,1");
    oscli_c("FX 113,2");
    vdu(12, -1);
    oscli_c("FX 112,1");
    oscli_c("FX 113,2");
}
#else
/* !Run's steps before OBJECT */
static void setup(void)
{
    /* BASIC SCREENLOAD: MODE 13, the title picture into bank 2 (&1FEC000,
     * 160K of screen ending at &2000000), then *FX 112,1 and *FX 113,2 */
    mode(15);
    mode(13);
    off();
    R[0] = roger_scratch("<SALOON2$DIR>.SALOON"); R[1] = 0x1FEC000;
    roger_swi(0xCD100);                          /* LZWD_Decompress */
    oscli_c("FX 112,1");
    oscli_c("FX 113,2");
    /* Sounds.Sounds: the voice modules are loaded already (gen/modules.inc) */
    oscli_c("PRINT <SALOON2$DIR>.RACECHAR");
}
#endif

static void init(void)
{
    bas_sys_idle = 200;                          /* a loop polling SYS "OS_Mouse" lets time pass */
    setup();
    object();
    bas_main();                                  /* RACE */
    roger_finish("program ended");
}

static struct roger_config config = {
    .title = DELUXE ? "Saloon Cars Deluxe (recompiled)" : "Saloon Cars (recompiled)",
    /* controllers: the keyboard controls (Control Menu, Keyboard - the
     * mouse is the default): Z/X steer, Page Down accelerates, Copy (End)
     * brakes, Delete kickdown, up/down change gear (D-pad); and S starts
     * the engine, D drive, R reverse, N neutral, H the handbrake */
    .pad_map = "left=Z,right=X,a=PageDown,b=End,x=Delete,y=H,lb=S,rb=D,lt=R,rt=N",
    .image_path = "../unpacked/code",
    .image = &recomp_image,
    .modules = modules,
    .appdir = "../game",
    .dir_prefixes = prefixes,
    .variables = vars,
    .initial_mode = 13,
    /* Deluxe's !Run: WimpSlot -min 630K -max 1500K - the most, as on a 2MB
     * machine (its RACE then loads the 2MB version's cars) */
    .wimpslot = (DELUXE ? 1500 : 600) * 1024,
    .screen_size = 0x28000,                      /* !Run: Screensize 160K (Deluxe: SETMODE) */
    .interpret_gaps = 1,
    /* An 8MHz ARM2's speed. The race moves by the vsyncs since its last
     * frame, so it keeps time at any speed, but its engine note doesn't: it
     * sets the engine's amplitude and pitch once a frame as a new note,
     * which restarts the engine voice's sample - about 20 times a second on
     * an ARM2 (a race frame is ~200,000 instructions), 50 unthrottled,
     * which is only a 50Hz buzz. --mips=N to change it, 0 for flat out.
     * Deluxe paces itself: a race frame is at least two vsyncs (25 a
     * second, its notes with them, as on an ARM3) however fast the CPU. It
     * gets a fast machine's speed, at which it always keeps to that: past
     * about 10 MIPS it's the same game, and finite, the host sleeps through
     * its wait for the vsync rather than spinning in it */
    .mips = DELUXE ? 25 : 4.5,
    .init = init,
};

/* Deluxe saves (players, lap times, the settings) in a directory of its own,
 * not the first release's savedata/ (the same names, in other formats);
 * --save=DIR still overrides it */
int main(int argc, char **argv)
{
    char *args[argc + 2];
    int n = 0;
    args[n++] = argv[0];
    if (DELUXE) args[n++] = "--save=savedata-deluxe";
    for (int k = 1; k < argc; k++) args[n++] = argv[k];
    args[n] = NULL;
    roger_main(n, args, &config);
}
