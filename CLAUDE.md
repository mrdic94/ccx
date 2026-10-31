# CLAUDE.md — instrucciones para Claude Code

ccx es una TUI sobre tmux que da a Claude Code una barra lateral de sesiones. Lee [README.md](README.md) para saber qué hace, [docs/DECISIONES.md](docs/DECISIONES.md) para saber por qué está hecho así y [docs/PLATAFORMAS.md](docs/PLATAFORMAS.md) para el estado en cada sistema.

## Instalar ccx en el equipo del usuario

1. **Identifica el sistema:** `uname`, `/etc/os-release`, escritorio (`$XDG_CURRENT_DESKTOP`), Wayland o X11 (`$WAYLAND_DISPLAY`) y las terminales instaladas. Lee su sección en `docs/PLATAFORMAS.md`.
2. **Ejecuta `./install.sh`.** Si faltan requisitos, el script dice cómo instalarlos.
   - Las órdenes con `sudo` o `brew` **propónselas al usuario** para que las ejecute él (por ejemplo, con `! sudo apt install tmux xclip`). No las ejecutes por tu cuenta.
   - Si tmux es anterior a la 3.2, explica las opciones antes de hacer nada.
3. **Ejecuta `tests/smoke.sh`.** Tiene que dar `12 correctas, 0 fallidas`. Usa servidores tmux propios y un claude falso, así que es seguro.
4. **Pide al usuario las pruebas manuales** de la lista de `docs/PLATAFORMAS.md`: ratón, Alt+s, portapapeles, claude real y acceso del menú. Tú no puedes verlas.
5. **Aplica los ajustes propios de la plataforma** que indique `docs/PLATAFORMAS.md`. Por ejemplo, Option como Meta en macOS, o los atajos de menú de GNOME Terminal en Mint. Son cambios en la configuración de la terminal del usuario: explícaselos en lugar de cambiarlos tú.
6. **Actualiza `docs/PLATAFORMAS.md`** con lo que hayas comprobado: pon el sistema como probado o anota los problemas. Propón al usuario hacer commit.

En un sistema "sin probar", si algo falla, arréglalo en el repositorio (no en la copia instalada: son enlaces simbólicos al repo) y documenta el cambio.

## Reglas al trabajar en este repositorio

- **No cierres ni reinicies el ccx del usuario** (socket `ccx`): puede tener conversaciones de Claude en marcha, y `tmux -L ccx kill-server` o `ccx --kill` las mataría.
  - Para probar, usa siempre otro socket: `CCX_SOCKET=ccx-test`, o `tests/smoke.sh`, que usa `ccx-smoke`.
  - Para aplicar cambios de `sidebar.py` al ccx en marcha, usa `ccx --reload`: reinicia solo la barra y conserva las sesiones.
  - Los cambios de `tmux.conf` necesitan reiniciar el servidor. Díselo al usuario y que decida él.
- **Nunca uses `cc` como nombre de comando o alias:** taparía el compilador de C.
- **Solo biblioteca estándar de Python.** Nada de dependencias con pip.
- **Bash compatible con 3.2 (macOS):**
  - nada de `mapfile`, `${var,,}`, `declare -A` ni `readarray`;
  - nada de opciones exclusivas de GNU (`realpath -e`, `sleep infinity`, `sed -i` sin sufijo en scripts que vayan a macOS).
- **Prueba antes de dar algo por hecho:** `bash -n` en los scripts, `python3 -m py_compile share/sidebar.py` y `tests/smoke.sh`. Si añades funciones, amplía `tests/smoke.sh`.
- **Si tomas una decisión de diseño, añádela a `docs/DECISIONES.md`.** Si cambia el uso, actualiza el `README.md`.

## Cómo funciona por dentro (resumen)

- **`bin/ccx`:** arranca el servidor tmux (`-L ccx -f share/tmux.conf`) con la sesión `ccx`, cuyo primer panel ejecuta `sidebar.py` en un bucle que lo reinicia si falla. Después se conecta a ella. `--start-only` arranca sin conectarse; se usa en los tests.
- **`share/sidebar.py`:**
  - Lista las conversaciones leyendo `~/.claude/projects/*/*.jsonl`. Se fija en las líneas `ai-title`, `custom-title` y `summary`, y en los mensajes `user` y `assistant` (`cwd` y texto).
  - Las sesiones en marcha son paneles etiquetados con `@ccx_sid`. Las no visibles esperan en la sesión oculta `ccx-bg`.
  - Mostrar una sesión es hacer `swap-pane` con el panel derecho.
  - Instala hooks de tmux para plegar la barra (4 columnas) y desplegarla (50).
- **Variables útiles para pruebas:**
  - `CCX_SOCKET`: otro servidor tmux.
  - `CCX_CLAUDE`: un claude falso, como `tests/fakeclaude`.
  - `CCX_SHARE`: usar el `share/` del repo en vez del instalado.
- **Depurar:**
  - `tmux -L <socket> list-panes -a -F '#{session_name} #{pane_id} #{pane_width} #{@ccx_sid}'` muestra el estado.
  - `tmux -L <socket> capture-pane -p -t <pane>` muestra lo que se ve en un panel.
  - Para foco, tamaños y menús hace falta un cliente conectado. `tests/smoke.sh` lo simula con un segundo servidor tmux (`outer`) que se conecta al de prueba.
