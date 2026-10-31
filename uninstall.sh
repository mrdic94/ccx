#!/usr/bin/env bash
# Desinstala ccx. No toca tus conversaciones de Claude (~/.claude).
#
#   ./uninstall.sh          quita comando, enlaces y acceso del menú
#   ./uninstall.sh --purge  además borra la configuración (~/.config/ccx)
#
# Si ccx está en marcha con sesiones abiertas, ciérralo antes con «ccx --kill»
# (las conversaciones quedan guardadas y se pueden reanudar con «claude --resume»).
set -euo pipefail
SHARE="$HOME/.local/share"

if tmux -L ccx has-session 2>/dev/null; then
  echo "ccx está en marcha. Ciérralo primero con «ccx --kill» y vuelve a ejecutar este script."
  exit 1
fi

for f in "$HOME/.local/bin/ccx" "$SHARE/ccx" "$SHARE/icons/hicolor/scalable/apps/ccx.svg"; do
  if [ -L "$f" ]; then rm -f "$f"; echo "  quitado $f"; fi
done
if [ -f "$SHARE/applications/ccx.desktop" ]; then
  rm -f "$SHARE/applications/ccx.desktop"; echo "  quitado $SHARE/applications/ccx.desktop"
  command -v update-desktop-database >/dev/null && update-desktop-database "$SHARE/applications" 2>/dev/null || true
fi
if [ "${1:-}" = "--purge" ] && [ -d "$HOME/.config/ccx" ]; then
  rm -rf "$HOME/.config/ccx"; echo "  borrado $HOME/.config/ccx"
fi
echo "ccx desinstalado. El repositorio sigue donde estaba."
