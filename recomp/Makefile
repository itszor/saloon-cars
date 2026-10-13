# Static recompilation of Saloon Cars: the BASIC program RACE (basic.c, from
# $(SS)/tools/bas2c.py, on the BASIC runtime $(SS)/runtime/basic_runtime.c),
# the machine code and modules (gen/, from SuperSpider's analyse and gen via
# ../tools/images.py) and game.c, linked with libroger (the RISC OS runtime).
ROGER   ?= $(HOME)/stuff/libroger
SS      ?= $(HOME)/stuff/superspider
CC      ?= gcc
CFLAGS  ?= -O2 -g -w -fno-strict-aliasing $(if $(TRACE),-DRECOMP_TRACE)
GEN     := $(wildcard gen/*/code*.c) $(wildcard gen/*/entries.c)
OBJ     := $(GEN:.c=.o) basic.o basic_runtime.o game.o
LIBS    := $(shell pkg-config --libs sdl3) -lm -lpthread
INC     := -I$(ROGER)/include
PROG    := ../unpacked/race.bas

salooncars: $(OBJ) $(ROGER)/libroger.a
	$(CC) $(CFLAGS) -o $@ $(OBJ) $(ROGER)/libroger.a $(LIBS)

$(ROGER)/libroger.a: FORCE
	$(MAKE) -C $(ROGER) libroger.a

gen/%.o: gen/%.c $(ROGER)/include/roger_cpu.h
	$(CC) $(CFLAGS) $(INC) -c -o $@ $<

basic.c: $(PROG) $(SS)/tools/bas2c.py
	python3 -I $(SS)/tools/bas2c.py '$(PROG)' $@

%.o: %.c $(SS)/runtime/basic_runtime.h $(ROGER)/include/roger.h
	$(CC) $(CFLAGS) $(INC) -I$(SS)/runtime -c -o $@ $<

basic_runtime.o: $(SS)/runtime/basic_runtime.c $(SS)/runtime/basic_runtime.h $(ROGER)/include/roger.h
	$(CC) $(CFLAGS) $(INC) -I$(SS)/runtime -c -o $@ $<

# make regen: unpack (the game's own LZWD), analyse and translate the machine code
regen:
	python3 -I ../tools/images.py unpack analyse gen

# make basic: RACE and OBJECT detokenised into ../basic, to read
basic:
	mkdir -p ../basic
	python3 -I $(SS)/tools/detok.py ../unpacked/race.bas > ../basic/RACE.bas
	python3 -I $(SS)/tools/detok.py ../unpacked/object.bas > ../basic/OBJECT.bas

LOG ?= untranslated.log
roots:
	python3 -I ../tools/images.py roots $(LOG)

clean:
	rm -f gen/*/*.o *.o basic.c salooncars

.PHONY: FORCE basic regen roots clean

game.o: gen/modules.inc
