#!/bin/sh
# Install the public client only; the school platform is never downloaded.
set -eu

if [ "${1:-}" = "--help" ]; then
    printf '%s\n' 'Usage: sh install.sh [--skip-setup]' 'Installs the school CLI and starts the interactive setup when a terminal is available.'
    exit 0
fi
if [ "$#" -gt 1 ] || { [ "$#" -eq 1 ] && [ "$1" != "--skip-setup" ]; }; then
    printf '%s\n' 'Unknown option. Use --help.' >&2
    exit 1
fi

if command -v uv >/dev/null 2>&1; then
    UV_BIN=$(command -v uv)
elif [ -x "$HOME/.local/bin/uv" ]; then
    UV_BIN="$HOME/.local/bin/uv"
else
    printf '%s\n' '正在安装 uv，用于管理客户端运行环境……'
    UV_INSTALLER=$(mktemp)
    trap 'rm -f "$UV_INSTALLER"' EXIT HUP INT TERM
    curl -fsSL https://astral.sh/uv/install.sh -o "$UV_INSTALLER"
    sh "$UV_INSTALLER"
    UV_BIN="$HOME/.local/bin/uv"
    if [ ! -x "$UV_BIN" ]; then
        printf '%s\n' '未找到 uv，请按 uv 安装提示重新打开终端后重试。' >&2
        exit 1
    fi
fi

SOURCE=https://github.com/ai-shifu/ai-shifu-for-school-cli/archive/refs/heads/main.zip
printf '%s\n' '正在安装学校 CLI 和配套 Skills 资源……'
"$UV_BIN" tool install --python 3.12 --reinstall "$SOURCE"
TOOL_BIN=$("$UV_BIN" tool dir --bin)
"$UV_BIN" tool update-shell
"$TOOL_BIN/ai-shifu-for-school" --version

if [ "${1:-}" != "--skip-setup" ] && ( : </dev/tty ) 2>/dev/null; then
    "$TOOL_BIN/ai-shifu-for-school" setup </dev/tty
else
    printf '%s\n' 'CLI 安装完成。请在终端执行 ai-shifu-for-school setup，完成域名、Skills 和账号配置。'
fi
