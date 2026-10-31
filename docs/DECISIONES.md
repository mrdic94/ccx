# Decisiones de diseño

Por qué ccx está hecho como está. Cada apartado indica la decisión, el motivo y lo que se descartó. Si cambias algo de esto, actualiza el apartado.

## 1. Objetivo

Reproducir en la terminal lo que ofrece la app de escritorio de Claude Code y falta en el modo terminal:

- ver las conversaciones anteriores en una lista a la izquierda;
- cambiar de una a otra **mientras siguen ejecutándose**;
- buscar entre ellas.

En Linux no hay app de escritorio, y el modo "local" de claude.ai/code solo funciona a través de ella. *Remote Control* (`claude --remote-control`) permite manejar desde la web una sesión que corre en tu PC, pero solo muestra las sesiones conectadas, no tu historial.

## 2. Herramientas existentes: por qué no ccmanager

Antes de escribir nada se revisó **ccmanager** (kbwo/ccmanager), la alternativa más recomendada. Es segura: no hace llamadas de red y el binario que distribuye coincide con su código. Pero no encaja con lo que se buscaba:

- organiza **una sesión por worktree de git**, no por conversación;
- no muestra el historial de conversaciones;
- al reabrirlo relanza `claude` sin recuperar la conversación;
- es un menú a pantalla completa, sin barra lateral.

Se miraron también otras herramientas por encima (claude-squad, ccmgr, cc-session-control, claude-sessions). Ninguna combinaba barra lateral persistente, historial y sesiones vivas.

## 3. tmux como base

**Decisión:** cada sesión de Claude corre en un panel de tmux. ccx es una capa fina encima de tmux.

**Motivo:** tmux ya resuelve lo difícil:

- emular la terminal de cada sesión;
- que los procesos sigan vivos aunque cierres la ventana;
- redimensionar;
- ratón y portapapeles.

Escribir un multiplexor propio (PTY + emulador de terminal en Python) sería mucho más código y peor.

**Descartado:** el TUI de ccmanager (ver §2) y un multiplexor propio.

## 4. Servidor tmux propio (`tmux -L ccx -f share/tmux.conf`)

**Decisión:** ccx usa su propio socket y su propia configuración.

**Motivo:** así no toca el tmux habitual del usuario, ni su `~/.tmux.conf`, ni sus atajos. Además puede imponer las opciones que necesita (sin prefijo, ratón, hooks) sin pisar nada. Los tests usan otros sockets (`ccx-smoke`, `ccx-test`) por la misma razón.

## 5. Dos sesiones tmux y `swap-pane`

**Decisión:**

- **`ccx`** es la sesión visible: una ventana con dos paneles, la barra a la izquierda y la conversación a la derecha.
- **`ccx-bg`** es una sesión oculta donde esperan, ejecutándose, las conversaciones que no se están viendo (una ventana por conversación).
- **Mostrar una conversación** consiste en intercambiar su panel con el de la derecha (`swap-pane`). El que estaba visible pasa a `ccx-bg`.

**Motivo:** `swap-pane` mueve el panel con su proceso intacto. Cambiar de sesión es instantáneo y nunca interrumpe a Claude.

**Detalles:**

- **Ventana guardiana:** la primera ventana de `ccx-bg` ejecuta `tail -f /dev/null` y nunca se mueve. Así la sesión oculta no desaparece cuando se vacía. Se usa `tail` y no `sleep infinity` porque este último no existe en macOS.
- **Aviso:** si no hay ninguna conversación abierta, a la derecha aparece un panel con el texto «Ninguna sesión abierta», etiquetado `__placeholder__`. Tiene el eco del teclado desactivado para que lo que teclees no ensucie la pantalla.
- **Tamaño de las ventanas ocultas:** se ajustan al tamaño del panel derecho (`resize-window`). Así Claude no tiene que redibujarse al traerlas.

## 6. El estado vive en tmux, no en ficheros

**Decisión:** cada panel lleva etiquetas como opciones de usuario de tmux:

| Etiqueta | Contenido |
|---|---|
| `@ccx_sid` | id de la conversación |
| `@ccx_title` | título que se muestra en el borde del panel |
| `@ccx_cwd` | carpeta de la conversación |
| `@ccx_started` | hora de inicio |

Hay además valores especiales: `__sidebar__`, `__placeholder__` y `__keeper__`.

**Motivo:** la barra lateral no guarda estado propio. Si se reinicia (tras un fallo o con `ccx --reload`), reconstruye todo preguntando a tmux, y las conversaciones abiertas no se pierden.

## 7. Leer directamente `~/.claude/projects/*/*.jsonl`

**Decisión:** la lista se construye leyendo los ficheros de conversación de Claude Code. De cada uno se toma:

- el título: `custom-title` > `ai-title` > `summary` > primer mensaje del usuario;
- la carpeta (`cwd`);
- el texto de los mensajes de usuario y asistente, para la búsqueda.

**Motivo:** es la única fuente que tiene todas las conversaciones de todos los proyectos. `claude --resume` no ofrece una salida para que la lea un programa.

**Riesgos y cómo se mitigan:**

- **Es un formato interno sin documentar y puede cambiar.** El lector es tolerante: ignora líneas que no entiende y solo usa campos concretos. Si un día la lista sale vacía o sin títulos, el sitio que hay que revisar es `parse_chunk()` en `sidebar.py`.
- **Rendimiento:**
  - lectura incremental (solo lo añadido desde la última vez);
  - solo las 400 conversaciones más recientes;
  - hasta 150 000 caracteres de texto por conversación para buscar;
  - se ignoran las conversaciones vacías, las de subagentes (`isSidechain`) y los mensajes de sistema.
- Respeta `CLAUDE_CONFIG_DIR` si está definido.

## 8. Cómo se lanza Claude

- **Conversación guardada:** `claude --resume <id>`, en su carpeta original. Por defecto `--resume` **reutiliza el mismo id**; para crear otro haría falta `--fork-session`. Así la lista no se duplica.
- **Conversación nueva:** `claude --session-id <uuid>`. ccx conoce el id antes de que exista el fichero, y la sesión aparece en la lista desde el primer momento.
- **Aviso de doble apertura:** si una conversación que ccx no tiene abierta se modificó hace menos de 90 s, probablemente está abierta en otra terminal. ccx pide confirmación, porque dos procesos escribiendo la misma conversación pueden mezclarla.

## 9. Teclado y ratón

- **Sin prefijo de tmux** (`prefix None`): Claude Code usa `Ctrl+B`, el prefijo por defecto de tmux. Con ccx no hace falta el prefijo; basta con atajos directos:
  - `Alt+s`: alternar entre la barra y la conversación;
  - `Alt+d`: salir.
- **Ratón activado:** clic para enfocar un panel o elegir una sesión, y rueda para desplazarse. Arrastrar copia al portapapeles mediante `copy-command`, que `bin/ccx` elige según el sistema: `wl-copy`, `xclip`, `xsel` o `pbcopy`. En terminales sin OSC 52, como las basadas en VTE, `set-clipboard` por sí solo no basta.
- **`escape-time 0`, `extended-keys` y `focus-events`:** para que Esc, Shift+Enter y el foco funcionen bien dentro de Claude.

## 10. Barra que se pliega sola

**Decisión:**

- **Desplegada (50 columnas):** cuando la barra tiene el foco.
- **Plegada (4 columnas):** cuando lo tiene la conversación. Solo muestra marcadores, alineados con la lista.

Hay hooks de tmux (`pane-focus-in`, `window-resized`, `client-resized` y `client-attached`) que ajustan el ancho, y la barra lo corrige además cuando recibe un cambio de tamaño.

**Motivo:** con ancho fijo, una barra ancha le quita sitio a la conversación y una estrecha no deja leer los títulos. La web y la app de escritorio lo resuelven con una barra plegable.

**Coste conocido:** al plegarse o desplegarse, el panel de Claude cambia de ancho y Claude se redibuja.

**Descartado por ahora:**

- **Barra flotante (`display-popup`):** no cambia el tamaño de nada, pero no permite ver de un vistazo qué hay en marcha. Es la alternativa si el redibujado molesta.
- **Barra fija con títulos en dos líneas.**

Al hacer clic en la barra plegada solo se despliega; no abre la conversación que haya en esa fila, para no abrir una sin querer.

## 11. Confirmaciones en una ventana centrada

**Decisión:** "Cerrar sesión" y "¿Abrir igualmente?" usan `display-menu` de tmux centrado en pantalla. Sus botones envían `s` o `n` a la barra mediante `send-keys`.

**Motivo:** en la línea inferior de la barra el texto no cabía. El menú de tmux sale centrado, admite teclado y ratón, y no necesita código de interfaz propio.

**Detalles:**

- Hace falta `--` antes de los elementos del menú, porque los elementos desactivados empiezan por `-` y tmux los leería como opciones.
- Si se cancela con Esc, la barra queda esperando respuesta hasta la siguiente tecla, que solo cancela. Es un efecto conocido y menor.

## 12. Python sin dependencias

**Decisión:** `sidebar.py` usa solo la biblioteca estándar (`curses`, `json`, `subprocess`…) y se ejecuta con `python3 -I`.

**Motivo:**

- No hay nada que instalar con `pip`.
- Funciona con el Python del sistema en Linux y macOS.
- `-I` aísla el script de `PYTHONPATH` y de los módulos del directorio actual.

**Si la barra falla:** el lanzador la reinicia en bucle y deja el error a la vista en el panel.

## 13. Instalación por enlaces simbólicos

**Decisión:** `install.sh` enlaza `~/.local/bin/ccx` y `~/.local/share/ccx` al repositorio.

**Motivo:**

- Actualizar es `git pull` + `ccx --reload`.
- Las rutas instaladas no cambian nunca, así que un servidor ccx en marcha sigue funcionando tras actualizar.
- No hace falta sudo.
- Todo es fácil de deshacer.

## 14. Ventana propia y terminal

**Decisión:** el acceso del menú ejecuta `share/ccx-window`, que usa preferentemente WezTerm con `--class ccx`.

**Motivo:** si la ventana tiene su propia clase o app-id, la barra de tareas la asocia a `ccx.desktop` y muestra el icono de ccx. Konsole y GNOME Terminal no permiten fijarla.

**Opciones de la ventana:**

- `window_close_confirmation=NeverPrompt`: cerrar la ventana solo desconecta de ccx, así que la pregunta "¿seguro?" sobra.
- `hide_tab_bar_if_only_one_tab`: para que no haya barra de pestañas.

Todas se pasan con `--config` y no tocan la configuración de WezTerm del usuario.

## 15. Nombre

Primero se llamó `ccs` ("Claude Code Sessions") y luego se renombró a **`ccx`** ("Claude Code eXtended"). Nunca `cc`, porque taparía el compilador de C (`/usr/bin/cc`).

"Claude" es una marca de Anthropic. Si el proyecto se hace público, el nombre público debe ser `ccx` sin explicar las siglas con la marca.
