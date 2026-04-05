# Battaglia Navale — Pyro5  (v2 con GUI)

## Avvio (3 terminali minimi)

```bash
# Terminale 1 — Name Server
python -m Pyro5.nameserver

# Terminale 2 — Server
python server.py

# Terminale 3 — Client A (GUI, default)
python client.py

# Terminale 4 — Client B (terminale)
python client.py --term
```

| Flag       | Modalità         |
|------------|------------------|
| *(nessuno)*| GUI  (tkinter)   |
| `--gui`    | GUI  (tkinter)   |
| `--term`   | Terminale        |

---

## Struttura file

| File                  | Dove gira | Ruolo |
|-----------------------|-----------|-------|
| `ship.py`             | Client    | Stato di una singola nave |
| `board.py`            | Client    | Griglia, calcolo colpi ricevuti, utility |
| `presets.py`          | Entrambi  | Configurazioni navi disponibili |
| `client_callback.py`  | Client    | Oggetto Pyro5 esposto + hook Observer |
| `client_terminal.py`  | Client    | Modalità terminale (hook → threading.Event) |
| `client_gui.py`       | Client    | Modalità GUI (hook → root.after) |
| `client.py`           | Client    | Entry point (sceglie la modalità) |
| `server.py`           | Server    | Coordinatore: turni, config, play again, log |

---

## Funzionalità nuove (v2)

### Scelta configurazione navi (distribuita)
Player 1 sceglie tra 3 preset (Classica 5 navi / Veloce 3 / Intensa 7).
Il server raccoglie la scelta e la trasmette a Player 2.
Entrambi usano la stessa configurazione — la configurazione nasce su un nodo,
transita per il server, arriva all'altro nodo.

### Rivincita
A fine partita entrambi vedono un dialogo "Vuoi rigiocare?".
Il server raccoglie i voti: se entrambi dicono Sì, resetta lo stato
e ri-invia la configurazione, riportando entrambi al piazzamento navi.

### Navi visibili durante la partita
- Griglia propria: ogni nave mostra le celle intatte/colpite/affondate.
- Pannello "navi nemiche affondate": si aggiorna ogni volta che si affonda
  una nave (il nome arriva nel risultato "sunk:NomeNave").

---

## Architettura distribuita

```
Client A  [Board A] [Daemon]          Server          Client B  [Board B] [Daemon]
      │                                  │                              │
      │── register_player(uri_A) ──────► │                              │
      │◄── notify_waiting_for_opponent ──│                              │
      │                                  │◄── register_player(uri_B) ───│
      │◄── notify_choose_config ─────────│─── notify_wait_config ──────►│
      │── submit_ship_config(...) ──────►│                              │
      │◄── notify_ship_config ───────────│─── notify_ship_config ──────►│
      │── player_ready() ───────────────►│◄── player_ready() ───────────│
      │◄── notify_game_start ────────────│─── notify_game_start ───────►│
      │◄── notify_your_turn ─────────────│                              │
      │── shoot("B5") ─────────────────►│                              │
      │                                  │─── receive_shot("B5") ──────►│
      │                                  │◄── "hit" ────────────────────│
      │◄── notify_shot_result ───────────│─── notify_opponent_shot ────►│
      │                                  │─── notify_your_turn ────────►│
      │ ... fine partita ...             │                              │
      │── vote_play_again(True) ────────►│◄── vote_play_again(True) ────│
      │◄── notify_play_again_result ─────│─── notify_play_again_result ►│
      │◄── notify_ship_config ───────────│─── notify_ship_config ──────►│
      │    (nuovo piazzamento)           │    (nuovo piazzamento)       │
```
