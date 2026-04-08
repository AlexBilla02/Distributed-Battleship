import tkinter as tk
from tkinter import ttk
import threading
import Pyro5.api
from board import Board
from ship  import Ship
from client_callback import ClientCallback
from presets import SHIP_PRESETS

# ── Palette colori ────────────────────────────────────────────────────────────
C = {
    "bg":       "#1e1e2e",
    "surface":  "#313244",
    "surface2": "#45475a",
    "water":    "#74c7ec",
    "ship":     "#abe0a7",
    "hit":      "#f38ba8",
    "miss":     "#585b70",
    "hover_ok": "#91e38a",
    "hover_bad":"#f38ba8",
    "hover_aim":"#f9e2af",
    "text":     "#cdd6f4",
    "subtext":  "#a6adc8",
    "accent":   "#89b4fa",
    "green":    "#a6e3a1",
    "red":      "#f38ba8",
    "yellow":   "#f9e2af",
    "border":   "#585b70",
}

CELL    = 36
HDR     = 24
LETTERS = "ABCDEFGHIJ"
GRID_PX = HDR + CELL * 10


# ─── Widget: Canvas Griglia ───────────────────────────────────────────────────

class GridCanvas(tk.Canvas):
    def __init__(self, parent, on_click=None, **kw):
        super().__init__(
            parent, width=GRID_PX, height=GRID_PX,
            bg=C["bg"], highlightthickness=1,
            highlightbackground=C["border"], **kw
        )
        self._on_click    = on_click
        self._rects       = {}
        self._colors      = {}
        self._hover_cells = []
        self._clickable   = False
        self._draw_grid()
        self.bind("<Button-1>", self._on_click_event)
        self.bind("<Leave>",    self._on_leave)

    def _draw_grid(self):
        for c in range(10):
            x = HDR + c * CELL + CELL // 2
            self.create_text(x, HDR // 2, text=str(c + 1),
                             fill=C["subtext"], font=("Segoe UI", 7))
        for r in range(10):
            y = HDR + r * CELL + CELL // 2
            self.create_text(HDR // 2, y, text=LETTERS[r],
                             fill=C["subtext"], font=("Segoe UI", 7))
        for r in range(10):
            for c in range(10):
                x1 = HDR + c * CELL
                y1 = HDR + r * CELL
                rid = self.create_rectangle(
                    x1, y1, x1 + CELL, y1 + CELL,
                    fill=C["water"], outline=C["border"], width=1,
                )
                self._rects[(r, c)]  = rid
                self._colors[(r, c)] = C["water"]

    def set_cell(self, r, c, color):
        self._colors[(r, c)] = color
        self.itemconfig(self._rects[(r, c)], fill=color)

    def set_clickable(self, val):
        self._clickable = val
        self.config(cursor="hand2" if val else "arrow")

    def cell_at(self, x, y):
        c = (x - HDR) // CELL
        r = (y - HDR) // CELL
        return (r, c) if (0 <= r < 10 and 0 <= c < 10) else None

    def set_hover(self, cells, color):
        for r, c in self._hover_cells:
            if (r, c) in self._rects:
                self.itemconfig(self._rects[(r, c)], fill=self._colors[(r, c)])
        self._hover_cells = [(r, c) for r, c in cells if (r, c) in self._rects]
        for r, c in self._hover_cells:
            self.itemconfig(self._rects[(r, c)], fill=color)

    def _on_click_event(self, event):
        if self._clickable:
            cell = self.cell_at(event.x, event.y)
            if cell and self._on_click:
                self._on_click(*cell)

    def _on_leave(self, event):
        self.set_hover([], C["water"])


# ─── Utility widget ───────────────────────────────────────────────────────────

def btn(parent, text, cmd, w=13, bg=None, fg=None, **kw):
    return tk.Button(
        parent, text=text, command=cmd,
        bg=bg or C["accent"], fg=fg or C["bg"],
        activebackground=C["surface2"], activeforeground=C["text"],
        relief="flat", bd=0, padx=10, pady=7,
        font=("Segoe UI", 10, "bold"), cursor="hand2", width=w, **kw
    )

def lbl(parent, text="", size=10, bold=False, color=None, bg=None, **kw):
    return tk.Label(
        parent, text=text,
        bg=bg or C["bg"], fg=color or C["text"],
        font=("Segoe UI", size, "bold" if bold else "normal"), **kw
    )

def frm(parent, bg=None, **kw):
    return tk.Frame(parent, bg=bg or C["bg"], **kw)


# ─── Applicazione principale ──────────────────────────────────────────────────

class BattleshipGUI(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Battaglia Navale")
        self.configure(bg=C["bg"])
        self.resizable(False, False)

        self.cb: ClientCallback | None = None
        self.server       = None
        self.player_id    = None
        self.daemon       = None
        self.board: Board | None = None
        self.ships_config = []
        self.opp_name     = ""
        self.my_turn      = False

        self._my_grid_cv  : GridCanvas | None = None
        self._trk_grid_cv : GridCanvas | None = None
        self._status_lbl  = None
        self._my_ship_rows: dict = {}
        self._opp_sunk_lbl= None
        self._opp_sunk    : list = []

        self._place_cv    : GridCanvas | None = None
        self._ship_queue  = []
        self._orient_h    = True
        self._queue_frame = None
        self._ready_btn   = None

        self._overlay: tk.Frame | None = None   # overlay play-again / negoziazione

        self._setup_callback()
        self._show_connect()

    # ── Setup hook ────────────────────────────────────────────────────────────

    def _setup_callback(self):
        self.cb = ClientCallback()
        cb = self.cb

        cb.on_waiting_for_opponent = lambda: self.after(0, self._show_waiting)
        cb.on_choose_config        = lambda: self.after(0, self._show_choose_config, False)
        cb.on_wait_config          = lambda: self.after(0, self._show_wait_config)

        def _on_proposal(cn, ships, proposer):
            self.after(0, self._show_config_proposal, cn, ships, proposer)

        cb.on_config_proposal = _on_proposal

        def _on_ship_config(cn, ships, board):
            self.ships_config = [tuple(s) for s in ships]
            self.board = board
            self.after(0, self._show_placement, cn)

        cb.on_ship_config = _on_ship_config

        def _on_game_start(opp):
            self.opp_name = opp
            self.after(0, self._show_game)

        cb.on_game_start = _on_game_start
        cb.on_your_turn  = lambda: self.after(0, self._enable_turn)

        cb.on_shot_result    = lambda c, r: self.after(0, self._apply_shot_result, c, r)
        cb.on_opponent_shot  = lambda c, r: self.after(0, self._apply_opp_shot, c, r)
        cb.on_game_over      = lambda won: self.after(0, self._show_game_over_overlay, won)
        cb.on_play_again_result = lambda r: self.after(0, self._handle_play_again, r)

    # ── Overlay helper ────────────────────────────────────────────────────────

    def _show_overlay(self, build_fn):
        """
        Mostra un frame semi-trasparente centrato sopra la finestra corrente.
        Non apre nessuna finestra separata: tutto rimane nella stessa finestra.
        """
        self._hide_overlay()
        overlay = tk.Frame(self, bg=C["surface"], bd=2, relief="flat",
                           highlightthickness=2, highlightbackground=C["accent"])
        self._overlay = overlay
        build_fn(overlay)
        # Centra nel contenuto della finestra principale
        self.update_idletasks()
        w = 360
        h = 260
        x = (self.winfo_width()  - w) // 2
        y = (self.winfo_height() - h) // 2
        overlay.place(x=x, y=y, width=w, height=h)

    def _hide_overlay(self):
        if self._overlay:
            self._overlay.destroy()
            self._overlay = None

    # ── Utility ───────────────────────────────────────────────────────────────

    def _clear(self):
        self._hide_overlay()
        for w in self.winfo_children():
            w.destroy()
        self._overlay = None

    # ══════════════════════════════════════════════════════════════════════════
    #  SCHERMATA 1: Connessione
    # ══════════════════════════════════════════════════════════════════════════

    def _show_connect(self):
        self._clear()
        self.geometry("380x280")
        pad = frm(self)
        pad.pack(expand=True)
        lbl(pad, "⚓ BATTAGLIA NAVALE", size=18, bold=True, color=C["accent"]).pack(pady=(30, 5))
        lbl(pad, "Il tuo nome:").pack()
        name_var = tk.StringVar(value="Giocatore")
        entry = tk.Entry(pad, textvariable=name_var, width=22,
                         bg=C["surface"], fg=C["text"], insertbackground=C["text"],
                         font=("Segoe UI", 11), relief="flat", bd=6)
        entry.pack(pady=8)
        entry.focus()
        err_lbl = lbl(pad, "", color=C["red"], size=9)
        err_lbl.pack(pady=2)

        def connect():
            name = name_var.get().strip() or "Giocatore"
            err_lbl.config(text="Connessione in corso...", fg=C["yellow"])
            connect_btn.config(state="disabled")
            threading.Thread(target=self._do_connect, args=(name,), daemon=True).start()

        connect_btn = btn(pad, "Connetti", connect, w=16)
        connect_btn.pack(pady=10)
        self.bind("<Return>", lambda e: connect())

    def _do_connect(self, name):
        try:
            self.daemon = Pyro5.api.Daemon(host="localhost")
            uri = self.daemon.register(self.cb)
            threading.Thread(target=self.daemon.requestLoop, daemon=True).start()
            with Pyro5.api.locate_ns() as ns:
                server_uri = ns.lookup("battleship.server")
            self.server    = Pyro5.api.Proxy(server_uri)
            self.player_id = self.server.register_player(name, str(uri))
        except Exception as e:
            self.after(0, lambda: self._connect_error(str(e)))

    def _connect_error(self, msg):
        from tkinter import messagebox
        messagebox.showerror("Errore connessione", msg)
        self._show_connect()

    # ══════════════════════════════════════════════════════════════════════════
    #  SCHERMATA 2a: Attesa avversario
    # ══════════════════════════════════════════════════════════════════════════

    def _show_waiting(self):
        self._clear()
        self.geometry("380x200")
        pad = frm(self)
        pad.pack(expand=True)
        lbl(pad, "⚓ BATTAGLIA NAVALE", size=16, bold=True, color=C["accent"]).pack(pady=(30, 20))
        lbl(pad, "⏳  In attesa dell'avversario...", size=11, color=C["yellow"]).pack()
        lbl(pad, "Il secondo giocatore deve connettersi.", size=9, color=C["subtext"]).pack(pady=8)

    # ══════════════════════════════════════════════════════════════════════════
    #  SCHERMATA 2b: Scelta / proposta configurazione
    # ══════════════════════════════════════════════════════════════════════════

    def _show_choose_config(self, is_counter_proposal=False):
        """
        Mostra il selettore preset.
        is_counter_proposal=True quando si sta facendo una contro-proposta.
        """
        self._clear()
        self.geometry("470x380")
        pad = frm(self)
        pad.pack(expand=True)

        title = "Contro-proposta configurazione" if is_counter_proposal else "Proponi una configurazione"
        lbl(pad, title, size=13, bold=True, color=C["accent"]).pack(pady=(20, 4))
        sub = "L'avversario potrà accettare o fare una contro-proposta." if not is_counter_proposal \
              else "L'avversario dovrà accettare o fare un'altra contro-proposta."
        lbl(pad, sub, size=9, color=C["subtext"]).pack(pady=(0, 16))

        choice = tk.StringVar(value=list(SHIP_PRESETS.keys())[0])

        for preset_name, ships in SHIP_PRESETS.items():
            row = frm(pad, bg=C["surface"])
            row.pack(fill="x", padx=20, pady=3)
            tk.Radiobutton(
                row, text=preset_name, variable=choice, value=preset_name,
                bg=C["surface"], fg=C["text"], selectcolor=C["surface2"],
                activebackground=C["surface"], activeforeground=C["accent"],
                font=("Segoe UI", 10, "bold"), anchor="w",
            ).pack(side="left", padx=8, pady=6)
            detail = ", ".join(f"{n}({s})" for n, s in ships)
            tk.Label(row, text=detail, bg=C["surface"], fg=C["subtext"],
                     font=("Segoe UI", 8)).pack(side="left", padx=4)

        info_lbl = lbl(pad, "", color=C["yellow"], size=9)
        info_lbl.pack(pady=6)

        def propose():
            cfg_name = choice.get()
            ships    = SHIP_PRESETS[cfg_name]
            info_lbl.config(text="Proposta inviata, in attesa dell'avversario...")
            propose_btn.config(state="disabled")
            threading.Thread(
                target=lambda: self.server.submit_ship_config(
                    self.player_id, cfg_name, list(ships)
                ), daemon=True
            ).start()
            # Mostra schermata attesa proposta
            self.after(200, self._show_wait_config)

        propose_btn = btn(pad, "Proponi", propose, w=16)
        propose_btn.pack(pady=12)

    # ══════════════════════════════════════════════════════════════════════════
    #  SCHERMATA 2c: Attesa proposta avversario
    # ══════════════════════════════════════════════════════════════════════════

    def _show_wait_config(self):
        self._clear()
        self.geometry("380x200")
        pad = frm(self)
        pad.pack(expand=True)
        lbl(pad, "⏳  In attesa della proposta...", size=12, color=C["yellow"]).pack(pady=(40, 10))
        lbl(pad, "L'avversario sta scegliendo la configurazione.", size=9, color=C["subtext"]).pack()

    # ══════════════════════════════════════════════════════════════════════════
    #  SCHERMATA 2d: Risposta alla proposta dell'avversario
    # ══════════════════════════════════════════════════════════════════════════

    def _show_config_proposal(self, config_name, ships, proposer_name):
        self._clear()
        self.geometry("470x400")
        pad = frm(self)
        pad.pack(expand=True)

        lbl(pad, f"Proposta di {proposer_name}", size=13, bold=True, color=C["accent"]).pack(pady=(20, 6))

        # Dettaglio config proposta
        box = frm(pad, bg=C["surface"])
        box.pack(fill="x", padx=24, pady=6)
        lbl(box, config_name, size=11, bold=True, color=C["yellow"], bg=C["surface"]).pack(pady=(8, 2))
        for name, size in ships:
            squares = "■" * size
            lbl(box, f"  {name} ({size})  {squares}", size=9,
                color=C["subtext"], bg=C["surface"]).pack(anchor="w", padx=16)
        lbl(box, "", bg=C["surface"]).pack(pady=4)

        lbl(pad, "Cosa vuoi fare?", size=10, color=C["text"]).pack(pady=10)

        btn_row = frm(pad)
        btn_row.pack()

        def accept():
            btn_accept.config(state="disabled")
            btn_counter.config(state="disabled")
            threading.Thread(
                target=lambda: self.server.accept_ship_config(self.player_id),
                daemon=True
            ).start()
            self.after(0, self._show_wait_config)

        def counter():
            self._show_choose_config(is_counter_proposal=True)

        btn_accept  = btn(btn_row, "✓ Accetta",       accept,  w=14, bg=C["green"], fg=C["bg"])
        btn_counter = btn(btn_row, "↺ Contro-proponi", counter, w=16, bg=C["surface2"], fg=C["text"])
        btn_accept.pack(side="left", padx=8)
        btn_counter.pack(side="left", padx=8)

    # ══════════════════════════════════════════════════════════════════════════
    #  SCHERMATA 3: Piazzamento navi
    # ══════════════════════════════════════════════════════════════════════════

    def _show_placement(self, config_name):
        self._clear()
        self.geometry("760x540")
        self.my_turn  = False
        self._opp_sunk = []
        self._my_ship_rows = {}

        self._ship_queue = list(self.ships_config)
        self._orient_h   = True

        top = frm(self)
        top.pack(fill="x", padx=16, pady=(12, 6))
        lbl(top, f"📌 Piazza le tue navi  —  {config_name}", size=12, bold=True,
            color=C["accent"]).pack(side="left")

        main = frm(self)
        main.pack(padx=16, pady=4)

        self._place_cv = GridCanvas(main, on_click=self._on_placement_click)
        self._place_cv.set_clickable(True)
        self._place_cv.pack(side="left", padx=(0, 20))
        self._place_cv.bind("<Motion>", self._on_placement_hover)

        right = frm(main)
        right.pack(side="left", fill="y")

        lbl(right, "Navi da piazzare:", bold=True, color=C["accent"]).pack(anchor="w")
        self._queue_frame = frm(right)
        self._queue_frame.pack(anchor="w", pady=(4, 16))

        orient_frame = frm(right)
        orient_frame.pack(anchor="w", pady=(0, 16))
        lbl(orient_frame, "Orientamento: ", color=C["subtext"]).pack(side="left")
        orient_var = tk.StringVar(value="Orizzontale")

        def toggle():
            self._orient_h = not self._orient_h
            orient_var.set("Orizzontale" if self._orient_h else "Verticale")

        btn(orient_frame, "↔ Ruota", toggle, w=10, bg=C["surface2"], fg=C["text"]).pack(side="left")
        lbl(orient_frame, "", textvariable=orient_var,
            color=C["yellow"]).pack(side="left", padx=6)

        self._ready_btn = btn(right, "✓ Pronto!", self._on_ready, w=16,
                              bg=C["surface2"], fg=C["subtext"])
        self._ready_btn.config(state="disabled")
        self._ready_btn.pack(pady=20)

        lbl(right, "Clicca sulla griglia per posizionare.", size=8, color=C["subtext"]).pack(anchor="w")
        lbl(right, "Verde = valido  |  Rosso = non valido", size=8, color=C["subtext"]).pack(anchor="w")

        self._refresh_queue_labels()

    def _refresh_queue_labels(self):
        for w in self._queue_frame.winfo_children():
            w.destroy()
        for i, (name, size) in enumerate(self._ship_queue):
            prefix = "▶" if i == 0 else "  "
            color  = C["accent"] if i == 0 else C["subtext"]
            lbl(self._queue_frame,
                f"{prefix} {name} ({size})  {'■' * size}",
                color=color, size=9 if i > 0 else 10, bold=(i == 0)).pack(anchor="w", pady=1)

    def _on_placement_hover(self, event):
        if not self._ship_queue:
            return
        cell = self._place_cv.cell_at(event.x, event.y)
        if not cell:
            self._place_cv.set_hover([], "")
            return
        r, c       = cell
        _, size    = self._ship_queue[0]
        cells      = self.board.get_placement_cells(r, c, size, self._orient_h)
        valid      = self.board.can_place(r, c, size, self._orient_h)
        valid_cells = [(rr, cc) for rr, cc in cells if 0 <= rr < 10 and 0 <= cc < 10]
        self._place_cv.set_hover(valid_cells, C["hover_ok"] if valid else C["hover_bad"])

    def _on_placement_click(self, r, c):
        if not self._ship_queue:
            return
        name, size = self._ship_queue[0]
        ship = Ship(name, size)
        if self.board.place_ship(ship, r, c, self._orient_h):
            for rr, cc in ship.cells:
                self._place_cv.set_cell(rr, cc, C["ship"])
            self._ship_queue.pop(0)
            self._refresh_queue_labels()
            if not self._ship_queue:
                self._place_cv.set_clickable(False)
                self._ready_btn.config(
                    state="normal", bg=C["green"], fg=C["bg"], cursor="hand2"
                )

    def _on_ready(self):
        self._ready_btn.config(state="disabled", text="In attesa...",
                               bg=C["surface2"], fg=C["subtext"])
        threading.Thread(
            target=lambda: self.server.player_ready(self.player_id),
            daemon=True
        ).start()

    # ══════════════════════════════════════════════════════════════════════════
    #  SCHERMATA 4: Partita
    # ══════════════════════════════════════════════════════════════════════════

    def _show_game(self):
        self._clear()
        self.geometry("940x640")

        top = frm(self, bg=C["surface"])
        top.pack(fill="x")
        lbl(top, "⚓ BATTAGLIA NAVALE", size=12, bold=True,
            color=C["accent"], bg=C["surface"]).pack(side="left", padx=14, pady=8)
        lbl(top, f"vs  {self.opp_name}", size=10, color=C["subtext"],
            bg=C["surface"]).pack(side="left", padx=4)
        self._status_lbl = lbl(top, "⏳ In attesa del turno...",
                                size=10, color=C["yellow"], bg=C["surface"])
        self._status_lbl.pack(side="right", padx=14)

        grids = frm(self)
        grids.pack(padx=14, pady=10)

        left = frm(grids)
        left.pack(side="left", padx=(0, 18))
        lbl(left, "TUA GRIGLIA", bold=True, color=C["subtext"]).pack(pady=(0, 4))
        self._my_grid_cv = GridCanvas(left)
        self._my_grid_cv.pack()
        for ship in self.board.ships:
            for r, c in ship.cells:
                self._my_grid_cv.set_cell(r, c, C["ship"])

        right_g = frm(grids)
        right_g.pack(side="left")
        lbl(right_g, "GRIGLIA AVVERSARIO", bold=True, color=C["subtext"]).pack(pady=(0, 4))
        self._trk_grid_cv = GridCanvas(right_g, on_click=self._on_shoot_click)
        self._trk_grid_cv.pack()
        self._trk_grid_cv.bind("<Motion>", self._on_aim_hover)

        # Pannello navi
        ship_panel = frm(self, bg=C["surface"])
        ship_panel.pack(fill="x", padx=14, pady=(0, 10))

        own_frame = frm(ship_panel, bg=C["surface"])
        own_frame.pack(side="left", padx=16, pady=8)
        lbl(own_frame, "Le tue navi:", bold=True, size=9,
            color=C["accent"], bg=C["surface"]).pack(anchor="w")
        self._my_ship_rows = {}
        for ship in self.board.ships:
            row_f = frm(own_frame, bg=C["surface"])
            row_f.pack(anchor="w", pady=1)
            l = lbl(row_f, self._ship_label(ship), size=8,
                    color=C["green"], bg=C["surface"])
            l.pack(side="left")
            self._my_ship_rows[ship.name] = (l, ship)

        opp_frame = frm(ship_panel, bg=C["surface"])
        opp_frame.pack(side="right", padx=16, pady=8)
        lbl(opp_frame, "Navi nemiche affondate:", bold=True, size=9,
            color=C["red"], bg=C["surface"]).pack(anchor="w")
        self._opp_sunk_lbl = lbl(opp_frame, "Nessuna ancora.", size=8,
                                  color=C["subtext"], bg=C["surface"])
        self._opp_sunk_lbl.pack(anchor="w")

    def _ship_label(self, ship):
        squares = ""
        for r, c in ship.cells:
            squares += "█" if self.board.my_grid[r][c] == "X" else "■"
        status = " (affondata)" if ship.is_sunk() else (" (colpita)" if ship.is_damaged() else "")
        return f"{'✗' if ship.is_sunk() else '▸'} {ship.name}  {squares}{status}"

    def _update_own_ship_labels(self):
        for name, (lbl_w, ship) in self._my_ship_rows.items():
            color = C["red"] if ship.is_sunk() else (C["yellow"] if ship.is_damaged() else C["green"])
            lbl_w.config(text=self._ship_label(ship), fg=color)

    def _update_opp_sunk_label(self):
        self._opp_sunk_lbl.config(
            text="\n".join(f"✗ {n}" for n in self._opp_sunk) if self._opp_sunk else "Nessuna ancora.",
            fg=C["red"] if self._opp_sunk else C["subtext"]
        )

    # ── Turno e sparo ─────────────────────────────────────────────────────────

    def _enable_turn(self):
        self.my_turn = True
        if self._trk_grid_cv:
            self._trk_grid_cv.set_clickable(True)
        if self._status_lbl:
            self._status_lbl.config(
                text="🎯 È IL TUO TURNO — clicca sulla griglia avversario",
                fg=C["green"]
            )

    def _disable_turn(self):
        self.my_turn = False
        if self._trk_grid_cv:
            self._trk_grid_cv.set_clickable(False)
        if self._status_lbl:
            self._status_lbl.config(text="⏳ Turno dell'avversario...", fg=C["yellow"])

    def _on_aim_hover(self, event):
        if not self.my_turn or not self._trk_grid_cv:
            return
        cell = self._trk_grid_cv.cell_at(event.x, event.y)
        if not cell:
            self._trk_grid_cv.set_hover([], "")
            return
        r, c = cell
        if self._trk_grid_cv._colors.get((r, c)) == C["water"]:
            self._trk_grid_cv.set_hover([(r, c)], C["hover_aim"])
        else:
            self._trk_grid_cv.set_hover([], "")

    def _on_shoot_click(self, r, c):
        if not self.my_turn:
            return
        if self._trk_grid_cv._colors.get((r, c)) != C["water"]:
            return
        coord = f"{LETTERS[r]}{c + 1}"
        self._disable_turn()
        threading.Thread(
            target=lambda: self.server.shoot(self.player_id, coord),
            daemon=True
        ).start()

    def _apply_shot_result(self, coord, result):
        base, ship_name = Board.parse_result(result)
        try:
            row, col = Board.parse_coord(coord)
        except ValueError:
            return
        color = C["hit"] if base in ("hit", "sunk", "sunk_all") else C["miss"]
        if self._trk_grid_cv:
            self._trk_grid_cv.set_cell(row, col, color)
        if base in ("sunk", "sunk_all") and ship_name:
            self._opp_sunk.append(ship_name)
            self._update_opp_sunk_label()

    def _apply_opp_shot(self, coord, result):
        base, _ = Board.parse_result(result)
        try:
            row, col = Board.parse_coord(coord)
        except ValueError:
            return
        color = C["hit"] if base in ("hit", "sunk", "sunk_all") else C["miss"]
        if self._my_grid_cv:
            self._my_grid_cv.set_cell(row, col, color)
        self._update_own_ship_labels()

    # ══════════════════════════════════════════════════════════════════════════
    #  Overlay: Fine partita (nella stessa finestra)
    # ══════════════════════════════════════════════════════════════════════════

    def _show_game_over_overlay(self, won: bool):
        """
        Mostra l'esito e il bottone rivincita come overlay sopra la griglia,
        senza aprire nessuna finestra separata.
        """
        emoji = "🏆" if won else "😢"
        msg   = "HAI VINTO!" if won else "HAI PERSO!"
        color = C["green"] if won else C["red"]

        def build(overlay):
            lbl(overlay, emoji, size=28, bg=C["surface"]).pack(pady=(20, 4))
            lbl(overlay, msg, size=16, bold=True, color=color, bg=C["surface"]).pack()
            lbl(overlay, "Vuoi giocare ancora?", size=10,
                color=C["subtext"], bg=C["surface"]).pack(pady=10)

            btn_row = frm(overlay, bg=C["surface"])
            btn_row.pack()

            def vote(v):
                self._hide_overlay()
                if self._status_lbl:
                    self._status_lbl.config(
                        text="⏳ In attesa del voto dell'avversario...", fg=C["yellow"]
                    )
                threading.Thread(
                    target=lambda: self.server.vote_play_again(self.player_id, v),
                    daemon=True
                ).start()

            btn(btn_row, "✓ Sì",  lambda: vote(True),  w=9, bg=C["green"], fg=C["bg"]).pack(side="left", padx=8)
            btn(btn_row, "✗ No",  lambda: vote(False), w=9, bg=C["red"],   fg=C["bg"]).pack(side="left", padx=8)

        self._show_overlay(build)

    def _handle_play_again(self, restart: bool):
        self._hide_overlay()
        if not restart:
            self._clear()
            self.geometry("380x180")
            pad = frm(self)
            pad.pack(expand=True)
            lbl(pad, "Grazie per aver giocato!", size=14, bold=True, color=C["accent"]).pack(pady=(40, 10))
            lbl(pad, "⚓", size=22).pack()
            btn(pad, "Esci", self.destroy, w=12).pack(pady=16)
        # Se restart=True: on_ship_config arriverà dal server → _show_placement
