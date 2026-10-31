#!/usr/bin/env bash
# Prueba de humo de ccx.
#
# Usa el código de ESTE repositorio (no el instalado), un «claude» falso y
# servidores tmux propios (ccx-smoke y ccx-smoke-outer), así que no toca tu ccx
# en marcha ni crea conversaciones. El servidor «outer» hace de cliente real
# conectado, necesario para que haya foco, tamaño de ventana y menús.
#
#   tests/smoke.sh        → sale con 0 si todo va bien
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd -P)"
export CCX_SOCKET=ccx-smoke CCX_SHARE="$REPO/share" CCX_CLAUDE="$REPO/tests/fakeclaude"
OUTER=ccx-smoke-outer

T() { tmux -L "$CCX_SOCKET" "$@"; }
O() { tmux -L "$OUTER" "$@"; }
pause() { python3 -c "import time; time.sleep(${1:-1})"; }
cleanup() { O kill-server 2>/dev/null; T kill-server 2>/dev/null; [ -n "${WORK:-}" ] && rm -rf "$WORK"; }
trap cleanup EXIT

PASS=0; FAIL=0
check() {
  local desc="$1"; shift
  if "$@"; then echo "  ✓ $desc"; PASS=$((PASS + 1)); else echo "  ✗ $desc"; FAIL=$((FAIL + 1)); fi
}

sidebar_id() { T list-panes -a -F '#{pane_id} #{@ccx_sid}' 2>/dev/null | awk '$2=="__sidebar__"{print $1}'; }
width()      { T display -p -t "$SIDEBAR" '#{pane_width}'; }
right_sid()  { T list-panes -t '=ccx:0' -F '#{pane_id} #{@ccx_sid}' | awk -v s="$SIDEBAR" '$1!=s{print $2}'; }
right_text() { T capture-pane -p -t "$(T list-panes -t '=ccx:0' -F '#{pane_id}' | grep -v "^$SIDEBAR\$")"; }
running()    { T list-panes -a -F '#{@ccx_sid}' | grep -v '^__' | grep -c . ; }
sidebar_has(){ T capture-pane -p -t "$SIDEBAR" | grep -q "$1"; }
screen_has() { O capture-pane -p | grep -q "$1"; }
is()         { [ "$1" = "$2" ]; }

cleanup
WORK="$(cd "$(mktemp -d)" && pwd -P)"
cd "$WORK"

echo "ccx — prueba de humo ($(tmux -V), $(python3 --version))"
env -u COLUMNS -u LINES "$REPO/bin/ccx" --start-only
O new-session -d -x 150 -y 30 "env -u TMUX tmux -L $CCX_SOCKET attach -t =ccx"
pause 2
SIDEBAR="$(sidebar_id)"

check "arranca la barra lateral"                      is "${SIDEBAR:+si}" si
check "a la derecha, el aviso de «ninguna sesión»"    is "$(right_sid)" __placeholder__
check "barra desplegada mientras tiene el foco (50)"  is "$(width)" 50

T send-keys -t "$SIDEBAR" n; pause 1
check "«n» pide el directorio"                         sidebar_has "Directorio:"
T send-keys -t "$SIDEBAR" C-u "$WORK" Enter; pause 1.5
check "la sesión nueva aparece a la derecha"           is "$(running)" 1
check "claude se lanza con --session-id"               eval 'right_text | grep -q -- "--session-id"'
check "… en el directorio pedido"                      eval 'right_text | grep -q "cwd: $WORK"'
check "barra plegada con el foco en la sesión (4)"     is "$(width)" 4

T select-pane -t "$SIDEBAR"; pause 1
check "barra desplegada al volver a ella"              is "$(width)" 50

T send-keys -t "$SIDEBAR" x; pause 1
check "«x» muestra la confirmación centrada"           screen_has "Cerrar sesión"
O send-keys s; pause 1.5
check "«Sí, cerrar» cierra la sesión"                  is "$(running)" 0
check "vuelve el aviso a la derecha"                   is "$(right_sid)" __placeholder__

echo
echo "$PASS correctas, $FAIL fallidas"
[ "$FAIL" -eq 0 ]
