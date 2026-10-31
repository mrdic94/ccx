#!/usr/bin/env python3
"""ccx — barra lateral de sesiones de Claude Code.

Se ejecuta en el panel izquierdo de la sesión tmux «ccx». Cada sesión de Claude
vive en su propio panel; las que no se están viendo esperan (y siguen
ejecutándose) en la sesión oculta «ccx-bg». Mostrar una sesión es intercambiar
su panel con el panel derecho (tmux swap-pane), así nunca se interrumpe.
"""
import curses
import glob
import json
import locale
import os
import shlex
import signal
import subprocess
import sys
import termios
import time
import unicodedata
import uuid

SOCK = os.environ.get("CCX_SOCKET", "ccx")
CLAUDE = os.environ.get("CCX_CLAUDE", "claude")
WIDTH = int(os.environ.get("CCX_WIDTH", "50"))   # barra desplegada (con el foco)
MINI = int(os.environ.get("CCX_MINI", "4"))       # barra plegada (foco en la conversación)
MAIN, BG = "ccx", "ccx-bg"
PROJECTS = os.path.join(os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude")), "projects")
PROJECT_FILE = os.path.expanduser("~/.config/ccx/project")
SELF = os.path.abspath(__file__)
PLACEHOLDER = "__placeholder__"
MAX_SESSIONS = 400       # sesiones más recientes que se listan
TEXT_CAP = 150_000       # caracteres de conversación por sesión usados para buscar
RESCAN_EVERY = 2.0       # segundos entre lecturas de ~/.claude/projects
RECENT_ELSEWHERE = 90    # s: si una sesión cerrada en ccx cambió hace menos, avisar


# ───────────────────────────── tmux ──────────────────────────────

def tmux(*args):
    r = subprocess.run(["tmux", "-L", SOCK, *args], capture_output=True, text=True, errors="replace")
    return r.returncode, r.stdout.strip()


def tmux_ok(*args):
    return tmux(*args)[0] == 0


ME = os.environ.get("TMUX_PANE", "")


def list_panes():
    """Todos los paneles del servidor ccx con sus etiquetas."""
    fmt = "\t".join(["#{pane_id}", "#{session_name}", "#{window_id}",
                     "#{@ccx_sid}", "#{@ccx_title}", "#{@ccx_cwd}", "#{@ccx_started}"])
    rc, out = tmux("list-panes", "-a", "-F", fmt)
    panes = []
    if rc == 0:
        for line in out.splitlines():
            f = line.split("\t")
            if len(f) == 7:
                panes.append(dict(id=f[0], session=f[1], window=f[2], sid=f[3],
                                  title=f[4], cwd=f[5], started=f[6]))
    return panes


def my_window(panes):
    for p in panes:
        if p["id"] == ME:
            return p["window"]
    return None


def right_pane(panes):
    win = my_window(panes)
    others = [p for p in panes if p["window"] == win and p["id"] != ME]
    return others[0] if others else None


def right_size():
    rc, out = tmux("display-message", "-p", "-t", MAIN + ":0", "#{window_width} #{window_height}")
    try:
        w, h = map(int, out.split())
        return str(max(20, w - MINI - 1)), str(max(5, h - 1))
    except ValueError:
        return "120", "40"


def tag(pane, **kv):
    for k, v in kv.items():
        tmux("set-option", "-p", "-t", pane, "@ccx_" + k, str(v))


def placeholder_cmd():
    return "python3 -I %s --placeholder" % shlex.quote(SELF)


def ensure_bg():
    if tmux_ok("has-session", "-t", "=" + BG):
        return
    w, h = right_size()
    # La primera ventana solo mantiene viva la sesión oculta; nunca se mueve.
    rc, pid = tmux("new-session", "-d", "-s", BG, "-x", w, "-y", h,
                   "-P", "-F", "#{pane_id}", "tail", "-f", "/dev/null")
    if rc == 0:
        tag(pid, sid="__keeper__", title="")


def ensure_layout():
    """Garantiza que a la derecha de la barra haya un panel (sesión o aviso)."""
    panes = list_panes()
    if right_pane(panes):
        return
    win = my_window(panes)
    ph = next((p["id"] for p in panes if p["sid"] == PLACEHOLDER and p["window"] != win), None)
    if not ph:
        ensure_bg()
        w, h = right_size()
        rc, ph = tmux("new-window", "-d", "-t", "=" + BG + ":", "-P", "-F", "#{pane_id}", placeholder_cmd())
        if rc != 0:
            return
        tag(ph, sid=PLACEHOLDER, title="")
    tmux("join-pane", "-h", "-d", "-s", ph, "-t", ME)
    tmux("resize-pane", "-t", ME, "-x", str(WIDTH))
    tmux("select-pane", "-t", ME)


def show_pane(pid):
    """Pone el panel pid a la derecha; el que había vuelve a segundo plano."""
    ensure_layout()
    right = right_pane(list_panes())
    if not right:
        return False
    if right["id"] != pid:
        if not tmux_ok("swap-pane", "-d", "-s", pid, "-t", right["id"]):
            return False
        w, h = right_size()
        tmux("resize-window", "-t", right["id"], "-x", w, "-y", h)
    tmux("select-pane", "-t", pid)
    return True


def spawn(argv, cwd, sid, title):
    ensure_bg()
    if not os.path.isdir(cwd):
        cwd = os.path.expanduser("~")
    w, h = right_size()
    rc, pid = tmux("new-window", "-d", "-t", "=" + BG + ":", "-c", cwd,
                   "-P", "-F", "#{pane_id}", *argv)
    if rc != 0 or not pid:
        return None
    tag(pid, sid=sid, title=title, cwd=cwd, started=int(time.time()))
    tmux("resize-window", "-t", pid, "-x", w, "-y", h)
    return pid


def fixed_project():
    """Proyecto fijo para sesiones nuevas (se guarda con «ccx --project»)."""
    try:
        with open(PROJECT_FILE, encoding="utf-8") as f:
            path = f.read().strip()
    except OSError:
        return ""
    return path if os.path.isdir(path) else ""


def install_hooks():
    """Barra desplegada mientras tiene el foco; plegada cuando lo tiene otro panel."""
    tag(ME, title="", sid="__sidebar__")
    hook = 'if-shell -F "#{==:#{pane_id},%s}" "resize-pane -t %s -x %d" "resize-pane -t %s -x %d"' % (
        ME, ME, WIDTH, ME, MINI)
    for name in ("pane-focus-in", "client-resized", "client-attached", "window-resized"):
        tmux("set-hook", "-g", name, hook)


def enforce_width():
    """Tras un cambio de tamaño de la ventana, devuelve la barra a su ancho."""
    rc, out = tmux("display-message", "-p", "-t", ME, "#{pane_active} #{pane_width}")
    try:
        active, width = out.split()
    except ValueError:
        return
    want = WIDTH if active == "1" else MINI
    if int(width) != want:
        tmux("resize-pane", "-t", ME, "-x", str(want))


# ─────────────────────── lectura de sesiones ───────────────────────

class Session:
    __slots__ = ("sid", "path", "cwd", "ai_title", "custom_title", "summary", "first_prompt",
                 "mtime", "size", "offset", "text", "norm")

    def __init__(self, path):
        self.path = path
        self.sid = os.path.basename(path)[:-6]
        self.cwd = self.ai_title = self.custom_title = self.summary = self.first_prompt = ""
        self.mtime = 0.0
        self.size = self.offset = 0
        self.text = []
        self.norm = None

    @property
    def title(self):
        t = self.custom_title or self.ai_title or self.summary or self.first_prompt or "(sin título)"
        return " ".join(t.split())

    @property
    def project(self):
        if self.cwd:
            return os.path.basename(self.cwd.rstrip("/")) or self.cwd
        return os.path.basename(os.path.dirname(self.path))

    def haystack(self):
        if self.norm is None:
            self.norm = normalize(" ".join([self.title, self.cwd, self.first_prompt, *self.text]))
        return self.norm


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content
                         if isinstance(b, dict) and b.get("type") == "text")
    return ""


def parse_chunk(s, data):
    added = sum(len(t) for t in s.text)
    for raw in data.split(b"\n"):
        if not raw:
            continue
        if b'"ai-title"' in raw or b'"custom-title"' in raw or b'"summary"' in raw[:60]:
            try:
                o = json.loads(raw)
            except ValueError:
                continue
            typ = o.get("type")
            if typ == "ai-title":
                s.ai_title = o.get("aiTitle") or s.ai_title
            elif typ == "custom-title":
                s.custom_title = o.get("customTitle") or o.get("title") or s.custom_title
            elif typ == "summary":
                s.summary = o.get("summary") or s.summary
            continue
        if b'"type":"user"' not in raw and b'"type":"assistant"' not in raw:
            continue
        try:
            o = json.loads(raw)
        except ValueError:
            continue
        typ = o.get("type")
        if typ not in ("user", "assistant") or o.get("isSidechain") or o.get("isMeta"):
            continue
        if not s.cwd and o.get("cwd"):
            s.cwd = o["cwd"]
        t = text_of((o.get("message") or {}).get("content")).strip()
        if not t or t.startswith("<") or t.startswith("[Request interrupted"):
            continue
        if typ == "user" and not s.first_prompt:
            s.first_prompt = t[:300]
        if added < TEXT_CAP:
            s.text.append(t[:TEXT_CAP - added])
            added += len(s.text[-1])


def refresh_session(s, st):
    if st.st_size == s.size and st.st_mtime == s.mtime:
        return
    if st.st_size < s.offset:                         # reescrito: empezar de cero
        s.__init__(s.path)
    try:
        with open(s.path, "rb") as f:
            f.seek(s.offset)
            data = f.read()
    except OSError:
        return
    end = data.rfind(b"\n") + 1                       # la última línea puede estar a medias
    parse_chunk(s, data[:end])
    s.offset += end
    s.size, s.mtime = st.st_size, st.st_mtime
    s.norm = None


class Store:
    def __init__(self):
        self.cache = {}

    def scan(self):
        found = []
        for path in glob.glob(os.path.join(PROJECTS, "*", "*.jsonl")):
            try:
                found.append((os.stat(path), path))
            except OSError:
                pass
        found.sort(key=lambda x: x[0].st_mtime, reverse=True)
        keep = {}
        for st, path in found[:MAX_SESSIONS]:
            s = self.cache.get(path) or Session(path)
            refresh_session(s, st)
            keep[path] = s
        self.cache = keep
        return [s for s in keep.values() if s.first_prompt or s.ai_title or s.custom_title]


# ──────────────────────────── utilidades ────────────────────────────

def normalize(s):
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def cwidth(ch):
    if unicodedata.combining(ch) or ch in "‍️":
        return 0
    return 2 if unicodedata.east_asian_width(ch) in "WF" else 1


def fit(s, width):
    """Recorta s a width columnas (con …) y rellena con espacios."""
    s = "".join(c if c.isprintable() else " " for c in s)
    out, used = [], 0
    for ch in s:
        w = cwidth(ch)
        if used + w > width:
            while out and used + 1 > width:
                used -= cwidth(out.pop())
            out.append("…")
            used += 1
            break
        out.append(ch)
        used += w
    return "".join(out) + " " * max(0, width - used)


def ago(ts):
    d = time.time() - ts
    if d < 60:
        return "ahora"
    if d < 3600:
        return "%d min" % (d // 60)
    if d < 86400:
        return "%d h" % (d // 3600)
    if d < 2 * 86400:
        return "ayer"
    if d < 7 * 86400:
        return "%d días" % (d // 86400)
    return time.strftime("%d/%m/%y", time.localtime(ts))


class Item:
    """Una fila de la lista: sesión guardada y/o en ejecución."""
    __slots__ = ("sid", "title", "cwd", "project", "mtime", "pane", "session")

    def __init__(self, sid, title, cwd, project, mtime, pane=None, session=None):
        self.sid, self.title, self.cwd, self.project = sid, title, cwd, project
        self.mtime, self.pane, self.session = mtime, pane, session


# ──────────────────────────── interfaz ────────────────────────────

class App:
    def __init__(self, scr):
        self.scr = scr
        self.store = Store()
        self.sessions, self.panes, self.items = [], [], []
        self.sel_sid = None
        self.top = 0
        self.query = ""
        self.mode = "list"            # list | search | input | confirm
        self.input_label = self.input_value = ""
        self.on_input = self.on_confirm = None
        self.msg, self.msg_until = "", 0.0
        self.last_scan = 0.0
        self.shown_sid = None
        self.seen_running = set()      # sesiones que han estado abiertas en ccx
        self.compact = False

    # ── datos
    def reload(self, rescan=False):
        if rescan or time.time() - self.last_scan > RESCAN_EVERY:
            self.sessions = self.store.scan()
            self.last_scan = time.time()
        self.panes = list_panes()
        right = right_pane(self.panes)
        self.shown_sid = right["sid"] if right else None
        if not right:
            ensure_layout()
            self.panes = list_panes()
        running = {p["sid"]: p for p in self.panes if p["sid"] and not p["sid"].startswith("__")}
        self.seen_running.update(running)
        items, seen = [], set()
        for s in self.sessions:
            p = running.get(s.sid)
            items.append(Item(s.sid, s.title, s.cwd, s.project, s.mtime, p and p["id"], s))
            seen.add(s.sid)
        for sid, p in running.items():          # sesiones nuevas aún sin fichero
            if sid not in seen:
                cwd = p["cwd"]
                items.append(Item(sid, p["title"] or "Nueva sesión", cwd,
                                  os.path.basename(cwd.rstrip("/")) or cwd,
                                  float(p["started"] or time.time()), p["id"]))
        items.sort(key=lambda i: i.mtime, reverse=True)
        if self.query:
            q = normalize(self.query)
            items = [i for i in items
                     if q in (i.session.haystack() if i.session else normalize(i.title + " " + i.cwd))]
        self.items = items
        if self.items and self.sel_sid not in {i.sid for i in self.items}:
            self.sel_sid = self.items[0].sid

    def sel_index(self):
        for n, i in enumerate(self.items):
            if i.sid == self.sel_sid:
                return n
        return 0

    def selected(self):
        return self.items[self.sel_index()] if self.items else None

    def move(self, delta):
        if self.items:
            n = max(0, min(len(self.items) - 1, self.sel_index() + delta))
            self.sel_sid = self.items[n].sid

    def flash(self, text, secs=3):
        self.msg, self.msg_until = text, time.time() + secs

    # ── acciones
    def open_item(self, item, force=False):
        if item.pane:
            if not show_pane(item.pane):
                self.flash("No se pudo mostrar la sesión")
            return
        if (not force and item.session and item.sid not in self.seen_running
                and time.time() - item.mtime < RECENT_ELSEWHERE):
            self.ask("Abrir sesión", ["«%s»" % item.title, "",
                                      "Parece abierta en otra terminal.",
                                      "Abrirla dos veces puede mezclar la conversación."],
                     "Abrir igualmente", lambda: self.open_item(item, force=True))
            return
        pid = spawn([CLAUDE, "--resume", item.sid], item.cwd or os.path.expanduser("~"),
                    item.sid, item.title)
        if not pid:
            self.flash("No se pudo lanzar claude")
            return
        time.sleep(0.15)
        if not show_pane(pid):
            self.flash("claude se cerró al arrancar (¿sesión dañada?)")
        self.reload()

    def new_session(self):
        cur = self.selected()
        default = (fixed_project() or (cur.cwd if cur and cur.cwd else "") or
                   os.environ.get("CCX_START_DIR") or os.path.expanduser("~"))

        def go(path):
            path = os.path.abspath(os.path.expanduser(path.strip() or default))
            if not os.path.isdir(path):
                self.flash("No existe el directorio: " + path)
                return
            sid = str(uuid.uuid4())
            pid = spawn([CLAUDE, "--session-id", sid], path, sid, "Nueva sesión")
            if pid and show_pane(pid):
                self.sel_sid = sid
            else:
                self.flash("No se pudo lanzar claude")
            self.reload()
        self.prompt("Directorio: ", default, go)

    def close_item(self, item):
        if not item.pane:
            self.flash("Esa sesión no está en ejecución")
            return

        def go():
            tmux("kill-pane", "-t", item.pane)
            ensure_layout()
            self.reload()
            self.flash("Sesión cerrada (sigue guardada en el historial)")
        self.ask("Cerrar sesión", ["«%s»" % item.title, "",
                                   "La conversación queda guardada en el historial."],
                 "Sí, cerrar", go)

    # ── diálogos
    def ask(self, title, lines, yes_label, on_yes):
        """Confirmación en una ventana centrada (menú de tmux). Sus botones envían
        «s» o «n» a esta barra, que sigue en modo confirmación mientras tanto."""
        self.mode, self.on_confirm = "confirm", on_yes
        self.input_label = "¿Confirmar?  s / n"
        rc, out = tmux("list-clients", "-t", "=" + MAIN, "-F", "#{client_name}")
        client = out.splitlines()[0] if rc == 0 and out else ""
        if not client:
            return                      # sin ventana conectada: queda la pregunta abajo

        def esc(s, n=60):
            s = " ".join(s.split())
            return (s[:n - 1] + "…" if len(s) > n else s).replace("#", "##")
        menu = ["display-menu", "-c", client, "-x", "C", "-y", "C",
                "-T", "#[align=centre] %s " % esc(title), "--"]   # «--»: los «-texto» no son opciones
        for line in lines:
            menu += ["-" + esc(line), "", ""]
        menu += ["",
                 yes_label, "s", "send-keys -t %s s" % ME,
                 "Cancelar", "n", "send-keys -t %s n" % ME]
        tmux(*menu)

    def prompt(self, label, value, on_done):
        self.mode, self.input_label, self.input_value, self.on_input = "input", label, value, on_done

    # ── dibujo
    def draw(self):
        scr = self.scr
        h, w = scr.getmaxyx()
        scr.erase()
        self.compact = w < 12
        if self.compact:
            self.draw_compact(h, w)
            return
        if h < 6:
            scr.refresh()
            return
        put = self.put
        running = sum(1 for i in self.items if i.pane)
        put(0, 0, fit(" Sesiones", w - 12), curses.A_BOLD | curses.color_pair(3))
        put(0, w - 12, fit(("%d activas" % running).rjust(11), 12), curses.A_DIM)
        if self.mode == "search":
            put(1, 0, fit(" / " + self.query + "▏", w))
        elif self.query:
            put(1, 0, fit(" / " + self.query + "   (Esc borra)", w), curses.color_pair(3))
        else:
            put(1, 0, fit(" / buscar", w), curses.A_DIM)

        rows = max(1, (h - 3) // 2)
        idx = self.sel_index()
        if idx < self.top:
            self.top = idx
        elif idx >= self.top + rows:
            self.top = idx - rows + 1
        self.top = max(0, min(self.top, max(0, len(self.items) - rows)))
        if not self.items:
            put(3, 0, fit("  Sin resultados" if self.query else "  No hay sesiones", w), curses.A_DIM)
        for n, item in enumerate(self.items[self.top:self.top + rows]):
            y = 2 + n * 2
            sel = item.sid == self.sel_sid
            base = curses.A_REVERSE if sel else 0
            if item.sid == self.shown_sid:
                mark, mattr = " ▶ ", curses.color_pair(1) | curses.A_BOLD
            elif item.pane:
                mark, mattr = " ● ", curses.color_pair(1)
            else:
                mark, mattr = "   ", 0
            put(y, 0, mark, mattr | base)
            put(y, 3, fit(item.title, w - 3), base | (curses.A_BOLD if item.pane else 0))
            put(y + 1, 0, fit("   %s · %s" % (item.project, ago(item.mtime)), w), base | curses.A_DIM)

        if self.mode == "confirm":
            put(h - 1, 0, fit(" " + self.input_label, w), curses.color_pair(2) | curses.A_BOLD)
        elif self.mode == "input":
            put(h - 1, 0, fit(" " + self.input_label + self.input_value + "▏", w), curses.color_pair(2))
        elif time.time() < self.msg_until:
            put(h - 1, 0, fit(" " + self.msg, w), curses.color_pair(2))
        else:
            put(h - 1, 0, fit(" ⏎ abrir  n nueva  x cerrar  q salir", w), curses.A_DIM)
        scr.refresh()

    def draw_compact(self, h, w):
        """Barra plegada: solo marcadores, en las mismas filas que la lista completa."""
        put = self.put
        put(0, 0, fit(" ≡", w), curses.A_BOLD | curses.color_pair(3))
        rows = max(1, (h - 3) // 2)
        for n, item in enumerate(self.items[self.top:self.top + rows]):
            y = 2 + n * 2
            if item.sid == self.shown_sid:
                put(y, 0, fit(" ▶", w), curses.color_pair(1) | curses.A_BOLD)
            elif item.pane:
                put(y, 0, fit(" ●", w), curses.color_pair(1))
            else:
                put(y, 0, fit(" ·", w), curses.A_DIM)
        put(h - 1, 0, fit(" »", w), curses.A_DIM)
        self.scr.refresh()

    def put(self, y, x, text, attr=0):
        try:
            self.scr.addstr(y, x, text, attr)
        except curses.error:
            pass                       # escribir en la última celda lanza error; es inocuo

    # ── teclado y ratón
    def key(self, k):
        if self.mode == "confirm":
            self.mode = "list"
            if k in ("s", "S", "y", "Y"):
                self.on_confirm()
            return
        if self.mode == "input":
            if k in ("\n", "\r", curses.KEY_ENTER):
                self.mode = "list"
                self.on_input(self.input_value)
            elif k == "\x1b":
                self.mode = "list"
            elif k in (curses.KEY_BACKSPACE, "\x7f", "\b"):
                self.input_value = self.input_value[:-1]
            elif k == "\x15":                       # Ctrl+U borra la línea
                self.input_value = ""
            elif isinstance(k, str) and k.isprintable():
                self.input_value += k
            return
        if self.mode == "search":
            if k in ("\n", "\r", curses.KEY_ENTER):
                self.mode = "list"
            elif k == "\x1b":
                self.mode, self.query = "list", ""
            elif k in (curses.KEY_BACKSPACE, "\x7f", "\b"):
                self.query = self.query[:-1]
            elif k in (curses.KEY_UP, curses.KEY_DOWN):
                self.mode = "list"
                self.key(k)
                return
            elif isinstance(k, str) and k.isprintable():
                self.query += k
            self.reload()
            return
        # modo lista
        item = self.selected()
        if k in (curses.KEY_UP, "k"):
            self.move(-1)
        elif k in (curses.KEY_DOWN, "j"):
            self.move(1)
        elif k == curses.KEY_PPAGE:
            self.move(-5)
        elif k == curses.KEY_NPAGE:
            self.move(5)
        elif k in (curses.KEY_HOME, "g"):
            self.move(-10 ** 6)
        elif k in (curses.KEY_END, "G"):
            self.move(10 ** 6)
        elif k in ("\n", "\r", curses.KEY_ENTER, curses.KEY_RIGHT, "l") and item:
            self.open_item(item)
        elif k == "\t":
            r = right_pane(list_panes())
            if r:
                tmux("select-pane", "-t", r["id"])
        elif k == "/":
            self.mode = "search"
        elif k == "\x1b":
            self.query = ""
            self.reload()
        elif k == "n":
            self.new_session()
        elif k == "x" and item:
            self.close_item(item)
        elif k == "r":
            self.reload(rescan=True)
            self.flash("Lista actualizada", 1)
        elif k == "q":
            tmux("detach-client", "-s", "=" + MAIN)
        elif k == curses.KEY_MOUSE:
            self.mouse()

    def mouse(self):
        try:
            _, x, y, _, bstate = curses.getmouse()
        except curses.error:
            return
        if self.compact:          # el clic solo sirve para desplegar la barra (lo hace tmux)
            return
        up = getattr(curses, "BUTTON4_PRESSED", 0x80000)
        down = getattr(curses, "BUTTON5_PRESSED", 0x200000)
        if bstate & up:
            self.move(-1)
        elif bstate & down:
            self.move(1)
        elif bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED | curses.BUTTON1_RELEASED):
            if y == 1:
                self.mode = "search"
                return
            h, _ = self.scr.getmaxyx()
            if 2 <= y < h - 1:
                n = self.top + (y - 2) // 2
                if n < len(self.items):
                    self.sel_sid = self.items[n].sid
                    if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_RELEASED):
                        self.open_item(self.items[n])

    def run(self):
        self.reload(rescan=True)
        self.draw()
        while True:
            try:
                k = self.scr.get_wch()
            except curses.error:
                k = None
            except KeyboardInterrupt:
                continue
            if k == curses.KEY_RESIZE:
                enforce_width()
            elif k is not None:
                self.key(k)
            self.reload()
            self.draw()


def placeholder():
    """Panel derecho cuando no hay ninguna sesión abierta."""
    try:
        attrs = termios.tcgetattr(0)
        attrs[3] &= ~(termios.ECHO | termios.ICANON)
        termios.tcsetattr(0, termios.TCSANOW, attrs)
    except termios.error:
        pass
    lines = ["Ninguna sesión abierta", "",
             "Elige una a la izquierda (Enter o clic)",
             "n  nueva sesión      /  buscar",
             "Alt+s  barra ⇄ sesión      Alt+d  salir"]

    def draw(*_):
        cols, rows = os.get_terminal_size()
        out = ["\x1b[2J\x1b[H\x1b[?25l", "\n" * max(0, rows // 2 - len(lines))]
        for n, l in enumerate(lines):
            style = "\x1b[1m" if n == 0 else "\x1b[2m"
            out.append(" " * max(0, (cols - len(l)) // 2) + style + l + "\x1b[0m\n")
        sys.stdout.write("".join(out))
        sys.stdout.flush()
    signal.signal(signal.SIGWINCH, draw)
    draw()
    while True:
        signal.pause()


def main(scr):
    curses.curs_set(0)
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)
    curses.init_pair(2, curses.COLOR_YELLOW, -1)
    curses.init_pair(3, curses.COLOR_CYAN, -1)
    curses.mousemask(curses.ALL_MOUSE_EVENTS)
    curses.mouseinterval(0)
    scr.timeout(1000)
    scr.keypad(True)
    App(scr).run()


if __name__ == "__main__":
    if "--placeholder" in sys.argv:
        placeholder()
    if not ME:
        sys.exit("ccx: sidebar.py se lanza desde el comando «ccx».")
    locale.setlocale(locale.LC_ALL, "")
    for var in ("LINES", "COLUMNS"):       # si están exportadas, curses ignora el tamaño real
        os.environ.pop(var, None)
    os.environ.setdefault("ESCDELAY", "25")
    install_hooks()
    ensure_layout()
    curses.wrapper(main)
