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
 * bas_main() is RACE. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "bas.h"

/* CODE's translation (make regen), at the address RACE's PROC_LOAD_CODE
 * decompresses it to (CODE_ADDRESS, ../tools/images.py). It's loaded up
 * front; the BASIC's LZWD_Decompress then writes the same bytes over it,
 * which leaves the translation in place. */
extern const struct roger_image recomp_image;

#include "gen/modules.inc"      /* LZWD and the voice modules; CODE_ADDRESS */

static const char *const vars[] = {
    "SALOON$DIR", "!Saloon",
    "SALOON2$DIR", "!Saloon.GameCode",
    "SALOON3$DIR", "!Saloon.Disc2",
    "SALOON4$DIR", "!Saloon.Sounds",
    NULL};
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

static void init(void)
{
    setup();
    object();
    bas_main();                                  /* RACE */
    roger_finish("program ended");
}

static struct roger_config config = {
    .title = "Saloon Cars (recompiled)",
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
    .wimpslot = 600 * 1024,
    .screen_size = 0x28000,                      /* !Run: Screensize 160K */
    .interpret_gaps = 1,
    /* An 8MHz ARM2's speed. The race moves by the vsyncs since its last
     * frame, so it keeps time at any speed, but its engine note doesn't: it
     * sets the engine's amplitude and pitch once a frame as a new note,
     * which restarts the engine voice's sample - about 20 times a second on
     * an ARM2 (a race frame is ~200,000 instructions), 50 unthrottled,
     * which is only a 50Hz buzz. --mips=N to change it, 0 for flat out */
    .mips = 4.5,
    .init = init,
};

int main(int argc, char **argv) { roger_main(argc, argv, &config); }
