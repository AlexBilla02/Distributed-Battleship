import Pyro5.api


@Pyro5.api.expose
class BattleshipServer:

    def __init__(self):
        self.players: dict       = {}
        self.player_order: list  = []
        self.turn_idx: int       = 0
        self.game_active: bool   = False
        self.match_log: list     = []
        self.ship_config         = None   # (config_name, ships) — configurazione navi accordata
        self.pending_config      = None   # (config_name, ships) — proposta configurazione navi
        self.pending_proposer    = None   # pid del proponente corrente
        self.play_again_votes: dict = {}


    def _proxy(self, pid: str) -> Pyro5.api.Proxy:
        """Proxy del giocatore nel corrente"""
        return Pyro5.api.Proxy(self.players[pid]["uri"])

    def _opponent(self, pid: str) -> str:
        """ritorna pid dell'avversario nel turno attuale"""
        return next(p for p in self.player_order if p != pid)

    #connessione giocatori
    def register_player(self, player_name: str, callback_uri: str) -> str:
        """
        il server rimane in attesa di due giocatori e salva l'uri di ognuno
        """
        if len(self.players) >= 2:
            raise Exception("Partita piena! Sono già connessi 2 giocatori.")

        pid = f"player_{len(self.players) + 1}"
        self.players[pid] = {"name": player_name, "uri": callback_uri, "ready": False}
        self.player_order.append(pid)
        print(f"[SERVER] '{player_name}' connesso ({pid}). {len(self.players)}/2")

        if len(self.players) == 1:
            self._proxy(pid).notify_waiting_for_opponent()
        else:
            # Entrambi connessi: Player 1 propone la configurazione per primo
            self._proxy(self.player_order[0]).notify_choose_config()
            self._proxy(pid).notify_wait_config()

        return pid

    #negoziazione configurazione
    def submit_ship_config(self, player_id: str, config_name: str, ships: list):
        """
        Un giocatore propone una configurazione all'avversario.
        L'avversario può accettarla con accept_ship_config() o fare
        una contro-proposta chiamando di nuovo submit_ship_config().
        Il ciclo continua finché uno dei due non accetta.
        """
        self.pending_config   = (config_name, list(ships))
        self.pending_proposer = player_id
        proposer_name = self.players[player_id]["name"]
        opponent_id   = self._opponent(player_id)
        print(f"[SERVER] '{proposer_name}' propone: '{config_name}'")
        self._proxy(opponent_id).notify_config_proposal(
            config_name, list(ships), proposer_name
        )

    def accept_ship_config(self, player_id: str):
        """
        Quando un giocatore accetta la proposta, il server la trasmette a entrambi i giocatori
        """
        if player_id == self.pending_proposer:
            raise Exception("Non puoi accettare la tua stessa proposta.")
        if self.pending_config is None:
            raise Exception("Nessuna proposta in corso.")
        config_name, ships = self.pending_config
        self.ship_config   = (config_name, list(ships))
        print(f"[SERVER] Config accettata: '{config_name}' — avvio piazzamento")
        for pid in self.player_order:
            self._proxy(pid).notify_ship_config(config_name, list(ships))

    def player_ready(self, player_id: str):
        if player_id not in self.players:
            raise Exception(f"player_id '{player_id}' non trovato.")
        self.players[player_id]["ready"] = True
        print(f"[SERVER] '{self.players[player_id]['name']}' è pronto.")
        if len(self.players) == 2 and all(p["ready"] for p in self.players.values()):
            self._start_game()

    
    def _start_game(self):
        """metodo chiamato quando entrambi i giocatori hanno piazzato le navi, viene comunicato il primo turno"""
        self.game_active = True
        names = [self.players[p]["name"] for p in self.player_order]
        print(f"\n[SERVER] ══ PARTITA INIZIATA: {names[0]} vs {names[1]} ══\n")
        for pid in self.player_order:
            opp_name = self.players[self._opponent(pid)]["name"]
            self._proxy(pid).notify_game_start(opp_name)
        self._proxy(self.player_order[self.turn_idx]).notify_your_turn()

    def shoot(self, attacker_id: str, coordinate: str):
        """metodo chiamato ad ogni colpo sparato
        """
        if not self.game_active:
            raise Exception("Partita non in corso.")
        if attacker_id != self.player_order[self.turn_idx]:
            raise Exception("Non è il tuo turno!")

        defender_id = self._opponent(attacker_id)
        attacker    = self.players[attacker_id]

        result   = self._proxy(defender_id).receive_shot(coordinate)
        base     = result.split(":")[0]
        turn_num = len(self.match_log) + 1
        self.match_log.append({
            "turn": turn_num, "attacker": attacker["name"],
            "coordinate": coordinate, "result": result,
        })
        print(f"[SERVER] T{turn_num:02d} | {attacker['name']:>12} → {coordinate:<3} → {result}")

        #all'attaccante si comunica l'esito chiamando notify_shot_result
        self._proxy(attacker_id).notify_shot_result(coordinate, result)
        #al difendente si comunica l'esito del colpo chiamando notify_opponent_shot
        self._proxy(defender_id).notify_opponent_shot(coordinate, result)


        #controllo se è finita la partita
        if base == "sunk_all":
            self.game_active = False
            print(f"\n[SERVER] ══ FINE PARTITA: vince {attacker['name']}! ══\n")
            self._proxy(attacker_id).notify_game_over(won=True)
            self._proxy(defender_id).notify_game_over(won=False)
        else:
            self.turn_idx = 1 - self.turn_idx
            self._proxy(self.player_order[self.turn_idx]).notify_your_turn()


    def vote_play_again(self, player_id: str, vote: bool):
        """metodo chiamato a fine partita per chiedere la rivincita"""
        self.play_again_votes[player_id] = vote
        name = self.players[player_id]["name"]
        print(f"[SERVER] '{name}' vuole rigiocare: {'Sì' if vote else 'No'}")
        if len(self.play_again_votes) == 2:
            restart = all(self.play_again_votes.values())
            print(f"[SERVER] Risultato rivincita: {'Sì' if restart else 'No'}")
            for pid in self.player_order:
                self._proxy(pid).notify_play_again_result(restart)
            if restart:
                self._reset_for_new_game()

    def _reset_for_new_game(self):
        """
        Reset dello stato per la nuova partita, l'unica cosa che tengo è la ocnfigurazione delle navi
        della partita appena giocata
        """
        self.game_active      = False
        self.turn_idx         = 0        
        self.match_log        = []
        self.play_again_votes = {}
        self.pending_config   = None
        self.pending_proposer = None
        for pid in self.player_order:
            self.players[pid]["ready"] = False
        self.player_order.reverse()

        #per mantenere la configurazione della partita precedente, togliere commenti qui e commentare la parte successiva
        #config_name, ships = self.ship_config
        #print(f"[SERVER] Reset — nuova partita con '{config_name}'")
        #for pid in self.player_order:
        #    self._proxy(pid).notify_ship_config(config_name, list(ships))
        #self.ship_config = None
        
        print(f"[SERVER] Reset — nuova negoziazione configurazione")
        self._proxy(self.player_order[0]).notify_choose_config()
        self._proxy(self.player_order[1]).notify_wait_config()

    def get_log(self) -> list:
        return list(self.match_log)

    def ping(self) -> str:
        return "pong"



def main():
    with Pyro5.api.Daemon(host="localhost") as daemon:
        with Pyro5.api.locate_ns() as ns:
            server = BattleshipServer()
            uri    = daemon.register(server)
            ns.register("battleship.server", uri)
            print("╔══════════════════════════════════════════╗")
            print("║   BATTAGLIA NAVALE  ·  SERVER  (Pyro5)   ║")
            print("╚══════════════════════════════════════════╝")
            print(f"  URI : {uri}")
            print("  In attesa di 2 giocatori...\n")
            daemon.requestLoop()


if __name__ == "__main__":
    main()
