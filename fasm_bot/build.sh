#!/usr/bin/env bash
# ==============================================================================
# build.sh — Скрипт сборки Telegram Schedule Bot (FASM x86_64 Linux)
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "=============================================================="
echo "  🚀 Сборка Telegram Schedule Bot (x86_64 FASM Linux)"
echo "=============================================================="

# 1. Проверка наличия fasm
if ! command -v fasm &> /dev/null; then
    echo "❌ [ОШИБКА] Flat Assembler (fasm) не найден!"
    echo ""
    echo "Установите fasm в вашей системе:"
    echo "  • Ubuntu/Debian : sudo apt-get update && sudo apt-get install -y fasm"
    echo "  • Arch Linux    : sudo pacman -S fasm"
    echo "  • Fedora / RHEL : sudo dnf install -y fasm"
    echo "  • Официальный   : https://flatassembler.net/download.php"
    exit 1
fi

# 2. Проверка наличия gcc
if ! command -v gcc &> /dev/null; then
    echo "❌ [ОШИБКА] Компилятор gcc не найден!"
    echo "Установите gcc: sudo apt-get install -y gcc (или build-essential)"
    exit 1
fi

# 3. Проверка libcurl
if ! pkg-config --exists libcurl 2>/dev/null && [ ! -f /usr/include/curl/curl.h ] && [ ! -f /usr/lib/*/libcurl.so ] && [ ! -f /usr/lib64/libcurl.so ]; then
    echo "⚠️  [ПРЕДУПРЕЖДЕНИЕ] Заголовочные файлы или библиотека libcurl могут отсутствовать."
    echo "Если линковка завершится с ошибкой, установите libcurl dev-пакет:"
    echo "  • Ubuntu/Debian : sudo apt-get install -y libcurl4-openssl-dev"
    echo "  • Arch Linux    : sudo pacman -S curl"
    echo "  • Fedora / RHEL : sudo dnf install -y libcurl-devel"
fi

echo "🔹 [1/2] Трансляция bot.asm через FASM..."
fasm bot.asm bot.o

echo "🔹 [2/2] Компоновка через GCC с libcurl..."
gcc -no-pie -O2 bot.o -lcurl -o bot

echo ""
echo "=============================================================="
echo "  ✅ Сборка успешно завершена: $(pwd)/bot"
echo "=============================================================="
echo ""
echo "Для запуска бота выполните:"
echo "  export BOT_TOKEN=\"ваш_токен_бота\""
echo "  ./bot"
echo ""
