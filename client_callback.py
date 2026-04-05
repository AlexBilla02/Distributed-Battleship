import Pyro5.api
from board import Board


@Pyro5.api.expose
class ClientCallback:
    """
    Il server ottiene un proxy di questo oggetto e lo chiama direttamente.
    """

    def __init__(self):
        self.board: Board | None = None

        # ho tutti gli attributi a None perché in base a se sto usando l'interfaccia da terminale o quella grafica
        # userò funzioni diverse, assegnate da client_terminal o client_gui
        self.on_waiting_for_opponent = None   # ()
        self.on_choose_config        = None   # ()
        self.on_wait_config          = None   # ()
        self.on_config_proposal      = None   # (config_name, ships, proposer_name)
        self.on_ship_config          = None   # (config_name, ships, board)
        self.on_game_start           = None   # (opp_name)
        self.on_your_turn            = None   # ()
        self.on_shot_result          = None   # (coord, result)
        self.on_opponent_shot        = None   # (coord, result)
        self.on_game_over            = None   # (won)
        self.on_play_again_result    = None   # (restart)


    def notify_waiting_for_opponent(self):
        if self.on_waiting_for_opponent:
            self.on_waiting_for_opponent()

    def notify_choose_config(self):
        if self.on_choose_config:
            self.on_choose_config()

    def notify_wait_config(self):
        if self.on_wait_config:
            self.on_wait_config()

    def notify_config_proposal(self, config_name: str, ships: list, proposer_name: str):
        """L'avversario ha proposto una configurazione: accetta o contro-proponi."""
        if self.on_config_proposal:
            self.on_config_proposal(config_name, list(ships), proposer_name)

    def notify_ship_config(self, config_name: str, ships: list):
        """Configurazione finale concordata"""
        self.board = Board()
        if self.on_ship_config:
            self.on_ship_config(config_name, list(ships), self.board)

    def notify_game_start(self, opponent_name: str):
        if self.on_game_start:
            self.on_game_start(opponent_name)

    def notify_your_turn(self):
        if self.on_your_turn:
            self.on_your_turn()

    def receive_shot(self, coordinate: str) -> str:
        return self.board.receive_shot(coordinate)

    def notify_shot_result(self, coordinate: str, result: str):
        self.board.mark_shot_fired(coordinate, result)
        if self.on_shot_result:
            self.on_shot_result(coordinate, result)

    def notify_opponent_shot(self, coordinate: str, result: str):
        if self.on_opponent_shot:
            self.on_opponent_shot(coordinate, result)

    def notify_game_over(self, won: bool):
        if self.on_game_over:
            self.on_game_over(won)

    def notify_play_again_result(self, restart: bool):
        if self.on_play_again_result:
            self.on_play_again_result(restart)

    def ping(self) -> str:
        return "alive"
