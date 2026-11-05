# ==============================================================================
# Dockerfile — Standalone Linux Build & Runtime for FASM Telegram Bot
# ==============================================================================
FROM ubuntu:22.04

# Установка зависимостей сборки
RUN apt-get update && apt-get install -y --no-install-recommends \
    fasm \
    gcc \
    make \
    ca-certificates \
    libcurl4-openssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копирование исходного кода
COPY . /app

# Сборка ассемблерного бота
RUN make clean && make

# Точка входа
CMD ["./bot"]
