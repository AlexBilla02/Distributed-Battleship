# Battaglia Navale — Pyro5

## Avvio

```bash
# Terminale 1 —  Avvia Name Server
python -m Pyro5.nameserver

# Terminale 2 — Avvia Server
python server.py

# Terminale 3 — Client A (Gui, default)
python client.py

# Terminale 4 — Client B (terminale)
python client.py --term
```

| Flag       | Modalità         |
|------------|------------------|
| *(nessuno)*| GUI              |
| `--gui`    | GUI              |
| `--term`   | Terminale        |

---

## Struttura file

| File                  | Dove gira | Ruolo |
|-----------------------|-----------|-------|
| `ship.py`             | Client    | Definizione classe nave |
| `board.py`            | Client    | Definizione classe Griglia, calcolo colpi ricevuti |
| `presets.py`          | Entrambi  | Configurazioni navi disponibili |
| `client_callback.py`  | Client    | Oggetto Pyro5 esposto  |
| `client_terminal.py`  | Client    | Modalità terminale |
| `client_gui.py`       | Client    | Modalità GUI  |
| `client.py`           | Client    | Entry point  |
| `server.py`           | Server    | Coordinatore: turni, config, play again, log |

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
