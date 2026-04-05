import threading
import Pyro5.api
from board import Board
from ship  import Ship
from client_callback import ClientCallback
from presets import SHIP_PRESETS



def place_ships_terminal(board: Board, ships_config: list):
    print("\n╔══════════════════════════════════════════╗")
    print("║          PIAZZAMENTO DELLE NAVI          ║")
    print("╚══════════════════════════════════════════╝")
    print("  Coordinata: lettera (A-J) + numero (1-10)  → es. B5")
    print("  Orientamento: O = orizzontale, V = verticale\n")
    for item in ships_config:
        name, size = item[0], item[1]
        board.display()
        print(f"  Piazza: {name}  (dimensione {size})")
        while True:
            try:
                coord  = input("    Coordinata iniziale : ").strip()
                orient = input("    Orientamento  (O/V) : ").strip().upper()
                if orient not in ("O", "V"):
                    raise ValueError("Usa O per orizzontale o V per verticale.")
                row, col = Board.parse_coord(coord)
                ship = Ship(name, size)
                if board.place_ship(ship, row, col, orient == "O"):
                    print(f"    ✓ {name} piazzata!\n")
                    break
                print("    ✗ Posizione non valida (fuori griglia o sovrapposta). Riprova.\n")
            except (ValueError, IndexError) as e:
                print(f"    ✗ Errore: {e}. Riprova.\n")
    board.display()
    print("  Tutte le navi piazzate! In attesa dell'avversario...\n")



def choose_config_terminal() -> tuple:
    """Scelta configurazione tra quelle del preset"""
    print("\n╔══════════════════════════════════════════╗")
    print("║       SCEGLI LA CONFIGURAZIONE           ║")
    print("╚══════════════════════════════════════════╝\n")
    presets = list(SHIP_PRESETS.items())
    for i, (name, ships) in enumerate(presets, 1):
        nomi = ", ".join(f"{n}({s})" for n, s in ships)
        print(f"  {i}. {name}")
        print(f"     {nomi}\n")
    while True:
        try:
            scelta = int(input(f"  Scegli (1-{len(presets)}): ").strip())
            if 1 <= scelta <= len(presets):
                nome, navi = presets[scelta - 1]
                return nome, navi
            print(f"  ✗ Inserisci un numero tra 1 e {len(presets)}.")
        except ValueError:
            print("  ✗ Inserisci un numero valido.")


def handle_proposal_terminal(config_name: str, ships: list, proposer_name: str) -> tuple:
    """
    Mostra la proposta dell'avversario e chiede se accettare o contro-proporre.
    """
    nomi = ", ".join(f"{n}({s})" for n, s in ships)
    print(f"\n  ══ PROPOSTA DI {proposer_name.upper()} ══")
    print(f"  Configurazione: {config_name}")
    print(f"  Navi: {nomi}\n")
    while True:
        scelta = input("  Accetti? (s = accetta / n = contro-proponi): ").strip().lower()
        if scelta == "s":
            return "accept", None, None
        if scelta == "n":
            print()
            nome, navi = choose_config_terminal()
            return "propose", nome, navi
        print("  ✗ Inserisci 's' per accettare o 'n' per contro-proporre.")



def run_terminal(player_name: str):
    cb     = ClientCallback()
    daemon = Pyro5.api.Daemon(host="localhost")
    uri    = daemon.register(cb)
    threading.Thread(target=daemon.requestLoop, daemon=True).start()
    print(f"[CLIENT] Daemon callback avviato.")

    ev_choose_config = threading.Event()   # server chiede di proporre
    ev_proposal      = threading.Event()   # ricevuta proposta dall'avversario
    ev_ship_cfg      = threading.Event()   # config finale concordata
    ev_game_start    = threading.Event()
    ev_turn          = threading.Event()
    ev_game_over     = threading.Event()
    ev_play_again    = threading.Event()

    shared = {}   # dati condivisi tra thread


    cb.on_waiting_for_opponent = lambda: print(
        "[SERVER] In attesa che l'avversario si connetta..."
    )

    cb.on_choose_config = lambda: ev_choose_config.set()

    cb.on_wait_config = lambda: print(
        "[SERVER] Attesa della proposta dal primo giocatore..."
    )

    def on_config_proposal(config_name, ships, proposer_name):
        shared["proposal"] = (config_name, list(ships), proposer_name)
        ev_proposal.set()

    cb.on_config_proposal = on_config_proposal

    def on_ship_config(config_name, ships, board):
        shared["config_name"] = config_name
        shared["ships"]       = ships
        shared["board"]       = board
        ev_ship_cfg.set()

    cb.on_ship_config = on_ship_config

    def on_game_start(opp_name):
        shared["opp_name"] = opp_name
        ev_game_start.set()

    cb.on_game_start = on_game_start
    cb.on_your_turn  = lambda: ev_turn.set()

    def on_shot_result(coord, result):
        base, ship_name = Board.parse_result(result)
        msgs = {
            "miss":     f"Acqua in {coord}.",
            "hit":      f"Colpito in {coord}! 💥",
            "sunk":     f"Hai affondato la {ship_name} in {coord}! 🚢💥",
            "sunk_all": f"Hai affondato tutte le navi nemiche! 🎉",
        }
        print(f"\n  ► {msgs.get(base, result)}")

    cb.on_shot_result = on_shot_result

    def on_opponent_shot(coord, result):
        base, ship_name = Board.parse_result(result)
        msgs = {
            "miss":     f"L'avversario ha mancato in {coord}.",
            "hit":      f"L'avversario ha colpito in {coord}! 💥",
            "sunk":     f"L'avversario ha affondato la {ship_name} in {coord}!",
            "sunk_all": f"Tutte le tue navi sono affondate!",
        }
        print(f"\n  ◄ {msgs.get(base, result)}")

    cb.on_opponent_shot = on_opponent_shot

    def on_game_over(won):
        shared["won"] = won
        ev_game_over.set()
        ev_turn.set()   # sblocca l'eventuale wait() nel loop di gioco

    cb.on_game_over = on_game_over

    def on_play_again_result(restart):
        shared["restart"] = restart
        ev_play_again.set()

    cb.on_play_again_result = on_play_again_result

    # ── Connessione al server
    with Pyro5.api.locate_ns() as ns:
        server_uri = ns.lookup("battleship.server")
    server    = Pyro5.api.Proxy(server_uri)
    player_id = server.register_player(player_name, str(uri))
    print(f"[CLIENT] Connesso come {player_id}.\n")

    # ── Negoziazione configurazione 
    if player_id == "player_1":
        ev_choose_config.wait()
        cfg_name, cfg_ships = choose_config_terminal()
        print(f"\n  ✓ Proposta inviata: {cfg_name}. In attesa dell'avversario...")
        server.submit_ship_config(player_id, cfg_name, cfg_ships)

    # Entrambi i giocatori entrano in questo loop:
    # - Chi ha proposto aspetta la risposta
    # - Chi ha ricevuto risponde
    while not ev_ship_cfg.is_set():
        triggered = threading.Event()

        def check():
            while not ev_ship_cfg.is_set() and not ev_proposal.is_set():
                import time; time.sleep(0.05)
            triggered.set()

        threading.Thread(target=check, daemon=True).start()
        triggered.wait()

        if ev_ship_cfg.is_set():
            break

        if ev_proposal.is_set():
            ev_proposal.clear()
            cfg_name, cfg_ships, proposer = shared["proposal"]
            action, new_name, new_ships = handle_proposal_terminal(
                cfg_name, cfg_ships, proposer
            )
            if action == "accept":
                server.accept_ship_config(player_id)
                # Aspetta notify_ship_config
            else:
                print(f"\n  ✓ Contro-proposta inviata: {new_name}. In attesa...")
                server.submit_ship_config(player_id, new_name, new_ships)

    while True:
        ev_ship_cfg.wait()
        ev_ship_cfg.clear()
        ev_game_over.clear()
        ev_turn.clear()   

        board = shared["board"]
        print(f"\n[SERVER] Configurazione: {shared['config_name']}")
        place_ships_terminal(board, shared["ships"])
        server.player_ready(player_id)

        ev_game_start.wait()
        ev_game_start.clear()
        print(f"[SERVER] Partita iniziata! Il tuo avversario è: {shared['opp_name']}\n")

        # Loop di gioco
        while not ev_game_over.is_set():
            ev_turn.wait()
            ev_turn.clear()
            if ev_game_over.is_set():
                break

            board.display()
            # Mostra stato navi proprie
            print("  Navi:")
            for ship in board.ships:
                stato = "✗ affondata" if ship.is_sunk() else ("~ colpita" if ship.is_damaged() else "● intatta")
                print(f"    {stato:15}  {ship.name}")
            print()
            print("  ══════ È IL TUO TURNO ══════")
            while True:
                try:
                    coord = input("  Coordinate (es. B5): ").strip()
                    Board.parse_coord(coord)
                    server.shoot(player_id, coord)
                    board.display()
                    break
                except ValueError:
                    print("  ✗ Coordinata non valida (es. B5). Riprova.")
                except Exception as e:
                    print(f"  ✗ {e}")

        # Fine partita
        ev_game_over.wait()
        board.display()
        if shared.get("won"):
            print("╔══════════════════════════════════════════╗")
            print("║           HAI VINTO! COMPLIMENTI!        ║")
            print("╚══════════════════════════════════════════╝\n")
        else:
            print("╔══════════════════════════════════════════╗")
            print("║           HAI PERSO! Alla prossima!      ║")
            print("╚══════════════════════════════════════════╝\n")

        voto = input("  Vuoi giocare ancora? (s/n): ").strip().lower() == "s"
        server.vote_play_again(player_id, voto)

        ev_play_again.wait()
        ev_play_again.clear()

        if not shared.get("restart"):
            print("\n  Grazie per aver giocato! Arrivederci.\n")
            break
        # Se restart: ev_ship_cfg sarà settato da notify_ship_config --> loop riparte

    daemon.shutdown()
