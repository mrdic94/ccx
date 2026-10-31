# ccx

**Sesiones de Claude Code con barra lateral, en la terminal.**

La app de escritorio de Claude Code tiene una lista de conversaciones a la izquierda y te deja saltar de una a otra mientras siguen trabajando. En Linux no hay app de escritorio, y en la terminal solo tienes `/resume`, que cambia de conversación pero no mantiene varias en marcha. ccx ofrece eso en la terminal: lista de sesiones, búsqueda, y varias sesiones ejecutándose a la vez.

```
Foco en la conversación              Foco en la barra (Alt+s o clic)
┌───┬────────────────────────┐       ┌──────────────────┬──────────┐
│ ≡ │ Ruta hasta Mordor      │       │ Sesiones 2 activ.│ Ruta ha… │
│   │                        │       │ / buscar         │          │
│ ● │  (conversación casi    │  ⇄    │ ● Queja: el agu… │          │
│   │   a pantalla completa) │       │   imperio · ahora│          │
│ ▶ │                        │       │ ▶ Ruta hasta Mor…│          │
│   │                        │       │   comarca · 5 min│          │
│ · │                        │       │   Calibrar el co…│          │
│   │                        │       │   delorean · ayer│          │
└───┴────────────────────────┘       └──────────────────┴──────────┘
  ▶ la que estás viendo   ● ejecutándose en segundo plano   · guardada
```

- Lista **todas** tus conversaciones de Claude Code, de todos los proyectos, con el título que les pone Claude.
- **Cambiar de sesión no interrumpe la anterior**: sigue trabajando en segundo plano.
- **Búsqueda** por título y por el texto de las conversaciones (sin distinguir tildes ni mayúsculas).
- La barra **se pliega sola** cuando trabajas en una conversación y se despliega cuando vuelves a ella.
- **Cerrar la ventana no cierra nada**: al volver a abrir ccx todo sigue como estaba.
- Sin dependencias aparte de tmux y Python 3 (solo la biblioteca estándar).

## Requisitos

| | Versión | Notas |
|---|---|---|
| [Claude Code](https://claude.com/claude-code) | cualquiera reciente | el comando `claude` |
| tmux | **3.2 o superior** | probado con 3.8 |
| Python 3 | 3.8+ con `curses` | viene con la mayoría de sistemas |
| Portapapeles | opcional | `wl-copy` (Wayland), `xclip`/`xsel` (X11), `pbcopy` (macOS) |

Estado por sistema: **Fedora KDE probado**; Linux Mint/Cinnamon y macOS **sin probar** (ver [docs/PLATAFORMAS.md](docs/PLATAFORMAS.md)).

## Instalación

```bash
git clone <url-del-repo> ~/ccx    # o donde prefieras
cd ~/ccx
./install.sh
```

`install.sh` comprueba los requisitos, te dice cómo instalar lo que falte y crea (sin sudo):

- `~/.local/bin/ccx` → enlace a `bin/ccx`
- `~/.local/share/ccx` → enlace a `share/`
- En Linux: el acceso **ccx** en el menú de aplicaciones con su icono (`--no-desktop` para omitirlo).

Son **enlaces simbólicos** al repositorio: no lo borres ni lo muevas después de instalar (si lo mueves, vuelve a ejecutar `./install.sh`).

Para comprobar que funciona en tu sistema sin tocar nada tuyo: `tests/smoke.sh`.

### Instalar con Claude Code

Abre `claude` en la carpeta del repositorio y pídele que instale ccx. [CLAUDE.md](CLAUDE.md) le explica el procedimiento, incluido qué hacer en sistemas aún no probados.

## Uso

```bash
ccx                 # abre ccx (o vuelve a él)
```

O busca **ccx** en el menú de aplicaciones.

| Tecla | Acción |
|---|---|
| `↑` `↓` / `j` `k` | moverse por la lista |
| `Enter` / clic | abrir la sesión (si ya está en marcha, cambia a ella al instante) |
| `n` | sesión nueva (pregunta la carpeta) |
| `x` | cerrar la sesión en marcha (queda guardada en el historial) |
| `/` | buscar · `Esc` borra la búsqueda |
| `Tab` | ir a la conversación |
| `Alt+s` | alternar entre barra y conversación |
| `Alt+d` / `q` | salir de ccx; **todo sigue ejecutándose** |
| `r` | releer la lista |

En la conversación funciona todo como en Claude Code normal, incluido `Ctrl+B` (ccx no usa el prefijo de tmux). Para seleccionar texto con el ratón: arrastrar copia al portapapeles; con `Shift` usas la selección nativa de tu terminal.

### Comandos

| Comando | |
|---|---|
| `ccx --project [carpeta]` | carpeta fija para las sesiones nuevas (sin argumento: la actual) |
| `ccx --no-project` | sin carpeta fija: `n` propone la de la sesión seleccionada |
| `ccx --reload` | recarga la barra lateral (tras actualizar) sin cerrar sesiones |
| `ccx --kill` | cierra ccx y **todas** las sesiones de Claude abiertas en él |

### Configuración

| Dónde | Para qué |
|---|---|
| `~/.config/ccx/project` | carpeta fija para sesiones nuevas (la escribe `ccx --project`) |
| `~/.config/ccx/terminal` | terminal que usa el acceso del menú (p. ej. `kitty`); si no, se detecta |
| `CCX_WIDTH` | ancho de la barra desplegada (50) |
| `CCX_MINI` | ancho de la barra plegada (4) |
| `CCX_TERMINAL` | como `~/.config/ccx/terminal`, pero por variable de entorno |
| `CLAUDE_CONFIG_DIR` | si usas una carpeta de Claude distinta de `~/.claude` |

Las variables `CCX_WIDTH`/`CCX_MINI` se leen al arrancar el servidor: tras cambiarlas, `ccx --kill` y vuelve a abrir.

## Actualizar

```bash
cd ~/ccx && git pull && ccx --reload
```

Si cambia `tmux.conf`, hace falta reiniciar el servidor: `ccx --kill` y `ccx` (cierra las sesiones abiertas; las conversaciones se conservan).

## Desinstalar

```bash
ccx --kill && ./uninstall.sh          # --purge borra también ~/.config/ccx
```

Tus conversaciones de Claude (`~/.claude`) no se tocan nunca.

## Problemas frecuentes

| Síntoma | Causa / solución |
|---|---|
| `ccx: command not found` | `~/.local/bin` no está en el `PATH`. Añade `export PATH="$HOME/.local/bin:$PATH"` a `~/.bashrc` o `~/.zshrc`. |
| Alt+s / Alt+d no hacen nada | La terminal se queda la tecla Alt (menús con Alt, u Option en macOS). Ver [docs/PLATAFORMAS.md](docs/PLATAFORMAS.md). |
| Aviso «Parece abierta en otra terminal» | La conversación se modificó hace menos de 90 s fuera de ccx. Abrirla dos veces a la vez puede mezclar la conversación. |
| La barra muestra un error de Python y se reinicia cada 3 s | Fallo en `sidebar.py`; el mensaje queda a la vista en el panel. Cópialo para corregirlo. |
| El acceso del menú no aparece | Cierra sesión y vuelve a entrar para que el escritorio recargue el menú. |
| En la barra de tareas sale el icono de la terminal | Solo WezTerm, kitty, alacritty y foot permiten el icono propio. Ver `~/.config/ccx/terminal`. |
| Texto duplicado o restos tras plegar/desplegar | Claude se redibuja al cambiar de ancho. Ver [DECISIONES §9](docs/DECISIONES.md). |

## Estructura

```
bin/ccx            lanzador: arranca/conecta el servidor tmux y opciones de línea de comandos
share/sidebar.py   la barra lateral (curses) y toda la lógica de paneles
share/tmux.conf    configuración del servidor tmux propio de ccx
share/ccx-window   abre ccx en una ventana de terminal (acceso del menú)
share/ccx.svg      icono
install.sh         instalación por enlaces simbólicos
uninstall.sh       desinstalación
tests/smoke.sh     prueba automática con un claude falso
tests/fakeclaude   el claude falso
LICENSE            licencia MIT
docs/DECISIONES.md por qué está hecho así
docs/PLATAFORMAS.md estado y pendientes por sistema operativo
CLAUDE.md          instrucciones para Claude Code (instalar, probar, modificar)
```

## Licencia

[MIT](LICENSE). ccx es un proyecto independiente, sin relación con Anthropic.
