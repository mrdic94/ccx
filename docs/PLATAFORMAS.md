# Plataformas

Estado de ccx en cada sistema y lo que falta desarrollar o probar. Al probar en un sistema nuevo, actualiza la tabla y la sección correspondiente.

| Sistema | Estado | Comentario |
|---|---|---|
| Fedora 44, KDE Plasma (Wayland) | ✅ **Probado** | tmux 3.8, Python 3.14, WezTerm y Konsole |
| Otras distros con KDE o GNOME | 🟡 Debería funcionar | mismas piezas; revisar la versión de tmux |
| Linux Mint, Cinnamon (X11) | 🟡 **Sin probar** | ver abajo: tmux, portapapeles y la tecla Alt en GNOME Terminal |
| macOS | 🟠 **Sin probar, con pendientes** | ver abajo: Option como Alt y no hay acceso en Launchpad |
| WSL (Windows) | ⚪ Sin probar | en teoría, como un Linux sin acceso de menú |

## Comprobación en un sistema nuevo

1. Ejecuta `./install.sh` y resuelve lo que indique.
2. Ejecuta `tests/smoke.sh`. Comprueba la lógica principal con un `claude` falso y tiene que salir **12 correctas, 0 fallidas**.
3. Pruebas a mano, que no se pueden automatizar:
   - [ ] `ccx` abre la barra y lista tus conversaciones con título.
   - [ ] Enter sobre una conversación la reanuda con el **claude real** y responde.
   - [ ] Cambiar a otra y volver: la primera sigue viva y en el mismo punto.
   - [ ] **Alt+s** alterna barra y conversación, y la barra se pliega y despliega.
   - [ ] **Clic** en la barra la despliega; clic en una fila abre esa conversación.
   - [ ] La **rueda del ratón** desplaza la lista y la conversación.
   - [ ] **Arrastrar** sobre texto de la conversación y pegarlo en otra aplicación (portapapeles).
   - [ ] `x` muestra la ventana centrada de confirmación y cierra la sesión.
   - [ ] **Alt+d** sale; al volver a `ccx`, todo sigue igual.
   - [ ] Acceso del menú: aparece al buscar "ccx", abre la ventana y muestra el icono (según la terminal).
4. Anota el resultado en la tabla de arriba.

## Linux Mint / Cinnamon

Lo que cambia respecto a Fedora KDE y hay que vigilar:

- **Versión de tmux:** hace falta la 3.2 o superior.
  - Mint 21.x (Ubuntu 22.04) trae 3.2a: vale.
  - Mint 22.x (Ubuntu 24.04) trae 3.4: vale.
  - Mint 20.x (Ubuntu 20.04) trae 3.0a: **no vale**. Habría que compilar tmux o usar un PPA o backport. `install.sh` lo detecta.
- **Paquetes:** `sudo apt install tmux xclip`. `python3` ya viene con `curses`.
- **Portapapeles:** Cinnamon usa X11, así que se usa `xclip` o `xsel`. `bin/ccx` lo detecta solo; si no hay ninguno, `install.sh` avisa.
- **Terminal:** la de Cinnamon es GNOME Terminal.
  - **Alt+s puede no llegar a ccx:** GNOME Terminal usa Alt+letra para abrir sus menús. Para que funcione: *Preferencias → General → desmarcar "Activar los atajos de teclado de los menús"*. Pendiente de confirmar en Mint.
  - **Icono:** en la barra de tareas saldrá el de GNOME Terminal. Para que salga el de ccx, instala WezTerm o kitty y escribe su nombre en `~/.config/ccx/terminal`.
- **Acceso del menú:** el `.desktop` en `~/.local/share/applications` es estándar y Cinnamon lo recoge. Si no aparece, cierra sesión y vuelve a entrar.
- **Sin probar en `share/ccx-window`:** las ramas de `gnome-terminal`, `xfce4-terminal`, `kitty`, `alacritty` y `foot`.

## macOS

Lo básico debería funcionar: tmux, Python y `curses` existen y los scripts son compatibles con bash 3.2. Quedan estos puntos:

- **Paquetes:**
  - `brew install tmux`.
  - Python 3: el de las *Command Line Tools* (`xcode-select --install`) o el de Homebrew. Los dos incluyen `curses`.
- **PATH:** `~/.local/bin` no está en el PATH por defecto. Añade a `~/.zshrc`: `export PATH="$HOME/.local/bin:$PATH"`. `bin/ccx` añade también `/opt/homebrew/bin` para encontrar tmux cuando se lanza fuera de una shell.
- **⚠️ Option como Alt (imprescindible para Alt+s y Alt+d):**
  - **Terminal.app:** *Ajustes → Perfiles → Teclado → "Usar Opción como tecla Meta"*.
  - **iTerm2:** *Settings → Profiles → Keys → Left Option key: Esc+*.
  - **WezTerm:** por defecto la Option izquierda ya envía Alt (`send_composed_key_when_left_alt_is_pressed = false`).
- **Portapapeles:** `pbcopy`, que viene de serie.
- **Acceso en Launchpad o Dock:** **pendiente**. `install.sh` no crea nada. Opciones a desarrollar:
  1. Una `.app` mínima con `osacompile` o Automator que ejecute `~/.local/share/ccx/ccx-window`.
  2. Empaquetar con Platypus.

  `share/ccx-window` ya tiene una rama para macOS, **sin probar**: usa WezTerm si está en `/Applications`; si no, Terminal.app mediante `osascript`. Con Terminal.app, cerrar la ventana pedirá confirmación porque hay un proceso en marcha; es inofensivo.
- **Sin probar:**
  - que `tests/smoke.sh` pase en macOS (usa `mktemp`, `env -u` y `awk`, que deberían ser compatibles);
  - el ratón y los menús de tmux en Terminal.app.
- **Ruta de las conversaciones:** la misma, `~/.claude/projects`.

## Diferencias que ya están resueltas en el código

| Problema | Solución |
|---|---|
| `sleep infinity` no existe en macOS | se usa `tail -f /dev/null` |
| `realpath -e` no existe en macOS | `cd "$dir" && pwd -P` |
| Portapapeles distinto en cada sistema | `bin/ccx` elige `wl-copy`, `xclip`, `xsel` o `pbcopy` al arrancar |
| PATH recortado al abrir desde el menú | `bin/ccx` añade `~/.local/bin`, `/opt/homebrew/bin` y `/usr/local/bin` |
| Variables de entorno no disponibles desde el menú | la terminal se puede fijar en `~/.config/ccx/terminal` |
