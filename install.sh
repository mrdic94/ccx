#!/usr/bin/env bash
# Instala ccx para el usuario actual (sin sudo). Compatible con bash 3.2 (macOS).
#
#   ./install.sh               instala o actualiza
#   ./install.sh --no-desktop  sin acceso en el menú de aplicaciones (Linux)
#
# Todo se instala como ENLACES SIMBÓLICOS a este repositorio, así que para
# actualizar basta con «git pull» y «ccx --reload». No mueve el repositorio
# después de instalar (o vuelve a ejecutar este script desde la nueva ruta).
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd -P)"
BIN="$HOME/.local/bin"
SHARE="$HOME/.local/share"
OS="$(uname)"
DESKTOP=1
[ "${1:-}" = "--no-desktop" ] && DESKTOP=0

ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; WARNINGS=$((WARNINGS + 1)); }
fail() { printf '  \033[31m✗\033[0m %s\n' "$*"; ERRORS=$((ERRORS + 1)); }
WARNINGS=0; ERRORS=0

pkg_hint() {   # cómo instalar un paquete en este sistema
  if [ "$OS" = Darwin ]; then echo "brew install $1"
  elif command -v dnf >/dev/null; then echo "sudo dnf install $1"
  elif command -v apt >/dev/null; then echo "sudo apt install $1"
  elif command -v pacman >/dev/null; then echo "sudo pacman -S $1"
  else echo "instala el paquete «$1»"; fi
}

echo "Comprobando requisitos…"

if command -v tmux >/dev/null; then
  v="$(tmux -V | sed -E 's/[^0-9]*([0-9]+)\.([0-9]+).*/\1 \2/')"
  major="${v% *}"; minor="${v#* }"
  if [ "$major" -gt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -ge 2 ]; }; then
    ok "$(tmux -V)"
  else
    fail "$(tmux -V): se necesita tmux 3.2 o superior"
  fi
else
  fail "falta tmux → $(pkg_hint tmux)"
fi

if command -v python3 >/dev/null; then
  if python3 -c 'import sys, curses; sys.exit(sys.version_info < (3, 8))' 2>/dev/null; then
    ok "$(python3 --version) con curses"
  else
    fail "python3 debe ser 3.8+ e incluir el módulo curses"
  fi
else
  fail "falta python3 → $(pkg_hint python3)"
fi

if command -v claude >/dev/null || [ -x "$HOME/.local/bin/claude" ]; then
  ok "claude encontrado"
else
  warn "no se encuentra «claude» (Claude Code). ccx lo necesita para abrir sesiones."
fi

if [ "$OS" = Darwin ]; then
  ok "portapapeles: pbcopy"
elif [ -n "${WAYLAND_DISPLAY:-}" ] && command -v wl-copy >/dev/null; then
  ok "portapapeles: wl-copy"
elif command -v xclip >/dev/null || command -v xsel >/dev/null; then
  ok "portapapeles: xclip/xsel"
elif [ -n "${WAYLAND_DISPLAY:-}" ]; then
  warn "sin portapapeles: copiar con el ratón no llegará al sistema → $(pkg_hint wl-clipboard)"
else
  warn "sin portapapeles: copiar con el ratón no llegará al sistema → $(pkg_hint xclip)"
fi

if [ "$ERRORS" -gt 0 ]; then
  echo; echo "Corrige lo anterior y vuelve a ejecutar ./install.sh"; exit 1
fi

# Enlaza dst → src. Si dst existe y no es un enlace, se guarda una copia.
link() {
  local src="$1" dst="$2"
  mkdir -p "$(dirname "$dst")"
  if [ -e "$dst" ] && [ ! -L "$dst" ]; then
    local bak="$dst.bak.$(date +%Y%m%d%H%M%S)"
    mv "$dst" "$bak"
    warn "ya existía $dst: lo he movido a $bak"
  fi
  ln -sfn "$src" "$dst"
}

echo "Instalando…"
chmod +x "$REPO/bin/ccx" "$REPO/share/ccx-window" "$REPO/tests/"*.sh "$REPO/tests/fakeclaude" 2>/dev/null || true
link "$REPO/bin/ccx" "$BIN/ccx"
ok "$BIN/ccx"
link "$REPO/share" "$SHARE/ccx"
ok "$SHARE/ccx → $REPO/share"

if [ "$OS" != Darwin ] && [ "$DESKTOP" = 1 ]; then
  link "$REPO/share/ccx.svg" "$SHARE/icons/hicolor/scalable/apps/ccx.svg"
  mkdir -p "$SHARE/applications"
  cat > "$SHARE/applications/ccx.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=ccx
GenericName=Sesiones de Claude Code
Comment=Sesiones de Claude Code con barra lateral
Exec=$SHARE/ccx/ccx-window
Icon=ccx
Terminal=false
Categories=Development;
Keywords=claude;sesiones;sessions;tmux;ai;
StartupNotify=true
StartupWMClass=ccx
EOF
  command -v update-desktop-database >/dev/null && update-desktop-database "$SHARE/applications" 2>/dev/null || true
  command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q "$SHARE/icons/hicolor" 2>/dev/null || true
  for k in kbuildsycoca6 kbuildsycoca5; do
    if command -v "$k" >/dev/null; then "$k" >/dev/null 2>&1 || true; break; fi
  done
  ok "acceso «ccx» en el menú de aplicaciones"
elif [ "$OS" = Darwin ]; then
  warn "macOS: no se crea acceso en Launchpad (pendiente, ver docs/PLATAFORMAS.md). Usa «ccx» en la terminal."
fi

case ":$PATH:" in
  *":$BIN:"*) ;;
  *) warn "$BIN no está en tu PATH. Añade a tu ~/.bashrc o ~/.zshrc:  export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac

if tmux -L ccx has-session 2>/dev/null; then
  "$BIN/ccx" --reload >/dev/null && ok "ccx estaba en marcha: barra lateral recargada"
fi

echo
if [ "$WARNINGS" -gt 0 ]; then echo "Instalado con $WARNINGS aviso(s). Ejecuta «ccx» para empezar."
else echo "Instalado. Ejecuta «ccx» para empezar."; fi
