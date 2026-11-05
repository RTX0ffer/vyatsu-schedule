# ==============================================================================
# Makefile for Telegram Schedule Bot (FASM x86_64 Linux)
# ==============================================================================

FASM   ?= fasm
CC     ?= gcc
CFLAGS ?= -no-pie -O2
LIBS   ?= -lcurl

TARGET = bot
ASM_SRC = bot.asm
INCLUDES = http_client.inc json_helper.inc schedule_data.inc
OBJ = bot.o

all: $(TARGET)

$(OBJ): $(ASM_SRC) $(INCLUDES)
	$(FASM) $(ASM_SRC) $(OBJ)

$(TARGET): $(OBJ)
	$(CC) $(CFLAGS) $(OBJ) $(LIBS) -o $(TARGET)

clean:
	rm -f $(TARGET) $(OBJ)

run: $(TARGET)
	@if [ -z "$$BOT_TOKEN" ]; then \
		echo "Ошибка: переменная BOT_TOKEN не задана!"; \
		echo "Пример: export BOT_TOKEN=\"123456:ABC...\" && make run"; \
		exit 1; \
	fi
	./$(TARGET)

.PHONY: all clean run
