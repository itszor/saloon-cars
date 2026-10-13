/* The game's own unpackers, run by libroger's ARM2 interpreter: nothing is
 * translated, every instruction is interpreted.
 *
 *   unpack --lzwd=MODULE IN=OUT...
 *       RMLoad the LZWD module (MODULE: the game's GameCode.LZWD) and
 *       decompress each IN with LZWD_Decompress (&CD100: R0 the file, R1
 *       where to, R2 the length out), writing the result to OUT. The game's
 *       code and its sound modules are kept compressed this way (!Run's
 *       Sounds loader, CUD, SCREENLOAD).
 *
 *   unpack FILE --stop=ADDR --dump=FROM:TO --write=OUT
 *       FILE loaded at &8000 and run; when control first reaches ADDR,
 *       [FROM, TO) is written to OUT. OBJECT (the program !Run RUNs) is
 *       Acorn-squeezed: its stub ends with `mov pc, r8` into the decoded
 *       image at &8000.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <roger.h>

#define BUF 0x10000                     /* where the Sounds loader decompresses to */
#define MODBASE 0x1800000

static uint8_t nocode[0x100000 / 32];
static struct roger_image image = {0x8000, 0x8000 + 0x80000, NULL, 0, nocode, 'P'};
static struct roger_image lzwd_image = {MODBASE, MODBASE, NULL, 0, nocode, 'L'};
static struct roger_module modules[2];

static uint32_t stop = ~0u, from, to;
static const char *out;
static const char *pairs[64];
static int npairs;

static int arg(const char *a)
{
    if (!strncmp(a, "--stop=", 7)) { stop = strtoul(a + 7, 0, 16); return 1; }
    if (!strncmp(a, "--dump=", 7)) {
        char *e;
        from = strtoul(a + 7, &e, 16);
        to = strtoul(e + 1, 0, 16);
        return 1;
    }
    if (!strncmp(a, "--write=", 8)) { out = a + 8; return 1; }
    return 0;
}

static void save(const char *path, uint32_t a, uint32_t n)
{
    FILE *f = fopen(path, "wb");
    if (!f) { perror(path); exit(1); }
    fwrite(MEM + a, 1, n, f);
    fclose(f);
}

static int stop_hook(uint32_t a)
{
    if (a != stop || !icount) return 0;
    save(out, from, to - from);
    printf("stopped at %08x after %llu instructions; wrote %08x-%08x to %s\n", a,
           (unsigned long long)icount, from, to, out);
    exit(0);
}

/* LZWD's SWI handler drops into the caller's mode (teqp with the PSR bits
 * of R14) and decompresses on the caller's stack: a user stack, as BASIC's */
static void lzwd_all(void)
{
    R[13] = 0x100000;
    for (int k = 0; k < npairs; k++) {
        char in[1024];
        const char *eq = strchr(pairs[k], '=');
        snprintf(in, sizeof in, "HostFS:%.*s", (int)(eq - pairs[k]), pairs[k]);
        R[0] = roger_scratch(in);
        R[1] = BUF;
        roger_swi(0xCD100 | 0x20000);                   /* XLZWD_Decompress */
        if (VF) { fprintf(stderr, "LZWD_Decompress %s: error %s\n", in, (char *)MEM + R[0] + 4); exit(1); }
        save(eq + 1, BUF, R[2]);
        printf("%-40s %6u bytes\n", eq + 1, R[2]);
    }
    exit(0);
}

static struct roger_config config = {
    .title = "unpack",
    .image = &image,
    .appdir = ".",
    .initial_mode = 13,
    .wimpslot = 0x100000 - 0x8000,
    .interpret_gaps = 1,
    .arg = arg,
    .call_addr = stop_hook,
    .usage = "  --lzwd=MODULE IN=OUT...  |  FILE --stop=ADDR --dump=FROM:TO --write=FILE   (hex addresses)\n",
};

int main(int argc, char **argv)
{
    char *args[64] = {argv[0], "--headless"};
    int n = 2;
    for (int k = 1; k < argc && n < 62; k++) {
        if (!strncmp(argv[k], "--lzwd=", 7)) {
            struct stat st;
            if (stat(argv[k] + 7, &st)) { perror(argv[k] + 7); return 1; }
            lzwd_image.end = MODBASE + (uint32_t)st.st_size;
            modules[0] = (struct roger_module){argv[k] + 7, &lzwd_image, 0};
            config.modules = modules;
            config.init = lzwd_all;
        } else if (argv[k][0] != '-' && strchr(argv[k], '=')) {
            pairs[npairs++] = argv[k];
        } else {
            if (argv[k][0] != '-') {                     /* the file: the (empty) image's extent */
                struct stat st;
                if (!stat(argv[k], &st)) image.end = 0x8000 + (uint32_t)st.st_size;
            }
            args[n++] = argv[k];
        }
    }
    if (config.init) args[n++] = "/dev/null";
    roger_main(n, args, &config);
}
