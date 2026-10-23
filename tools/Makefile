# tools/unpack: libroger's ARM2 interpreter running the game's own unpackers (see unpack.c).
ROGER   ?= $(HOME)/stuff/libroger
CC      ?= gcc

unpack: unpack.c $(ROGER)/libroger.a $(ROGER)/include/roger.h
	$(CC) -O2 -g -Wall -I$(ROGER)/include -o $@ unpack.c $(ROGER)/libroger.a $(shell pkg-config --libs sdl3) -ljpeg -lm -lpthread

$(ROGER)/libroger.a: FORCE
	$(MAKE) -C $(ROGER) libroger.a

clean:
	rm -f unpack

.PHONY: FORCE clean
