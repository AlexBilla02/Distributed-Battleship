from ship import Ship


class Board:
    SIZE    = 10
    LETTERS = "ABCDEFGHIJ"

    def __init__(self):
        """ my_grid è la mia griglia, tracking grid è la griglia avversaria che mi salvo per poter 
            visualizzare l'esito dei colpi che ho sparato fino a questo momento """
        self.my_grid       = [["~"] * self.SIZE for _ in range(self.SIZE)]
        self.tracking_grid = [["~"] * self.SIZE for _ in range(self.SIZE)]
        self.ships: list[Ship] = []
        self._shot_cells: set  = set()


    def place_ship(self, ship: Ship, row: int, col: int, horizontal: bool) -> bool:
        """metodo per piazzare navi su board, ~ sarà acqua, S cella con la nave, X colpita e O mancato"""
        cells = []
        for i in range(ship.size):
            r = row + (0 if horizontal else i)
            c = col + (i if horizontal else 0)
            if not (0 <= r < self.SIZE and 0 <= c < self.SIZE):
                return False
            if self.my_grid[r][c] != "~":
                return False
            cells.append((r, c))
        ship.place(cells)
        for r, c in cells:
            self.my_grid[r][c] = "S"
        self.ships.append(ship)
        return True

    def can_place(self, row: int, col: int, size: int, horizontal: bool) -> bool:
        """metodo che uso per la GUI per vedere se è possibile piazzare una nave in tutte le celle selezionate"""
        for i in range(size):
            r = row + (0 if horizontal else i)
            c = col + (i if horizontal else 0)
            if not (0 <= r < self.SIZE and 0 <= c < self.SIZE):
                return False
            if self.my_grid[r][c] != "~":
                return False
        return True

    def get_placement_cells(self, row: int, col: int, size: int, horizontal: bool) -> list:
        """metodo usato dalla GUI per ritornare le celle su cui si piazzerà la nave"""
        cells = []
        for i in range(size):
            r = row + (0 if horizontal else i)
            c = col + (i if horizontal else 0)
            cells.append((r, c))
        return cells


    def receive_shot(self, coordinate: str) -> str:
        """
        Il server chiama questo metodo quando l'altro client invia un colpo.
        Ritorna: 'miss' | 'hit' | 'sunk:NomeNave' | 'sunk_all:NomeNave'
        """
        try:
            row, col = self.parse_coord(coordinate)
        except ValueError:
            return "invalid"
        if (row, col) in self._shot_cells:
            return "already_shot"
        self._shot_cells.add((row, col))

        for ship in self.ships:
            if ship.occupies(row, col):
                ship.hit(row, col)
                self.my_grid[row][col] = "X"
                if ship.is_sunk():
                    suffix = f":{ship.name}"
                    return f"sunk_all{suffix}" if all(s.is_sunk() for s in self.ships) else f"sunk{suffix}"
                return "hit"

        self.my_grid[row][col] = "O"
        return "miss"


    def mark_shot_fired(self, coordinate: str, result: str):
        """metodo per segnare nella mia tracking grid, il risultato del mio ultimo colpo sparato"""
        try:
            row, col = self.parse_coord(coordinate)
        except ValueError:
            return
        base, _ = self.parse_result(result)
        self.tracking_grid[row][col] = "X" if base in ("hit", "sunk", "sunk_all") else "O"


    @staticmethod
    def parse_result(result: str) -> tuple:
        """
        splitto la stringa in input (ad esempio sunk:Corazzata --> 'sunk','Corazzata')
        """
        parts = result.split(":", 1)
        return parts[0], (parts[1] if len(parts) > 1 else "")

    @staticmethod
    def parse_coord(coordinate: str) -> tuple:
        """metodo statico per fare parsing dell'input delle coordinate"""
        c = coordinate.strip().upper()
        if len(c) < 2 or c[0] not in Board.LETTERS:
            raise ValueError(f"Lettera non valida: '{coordinate}'")
        row = Board.LETTERS.index(c[0])
        col = int(c[1:]) - 1
        if not (0 <= col < Board.SIZE):
            raise ValueError(f"Numero colonna fuori range: '{c[1:]}'")
        return row, col


    def display(self):
        nums   = " ".join(f"{i+1:2}" for i in range(self.SIZE))
        header = f"    {nums}"
        sep    = "      "
        lbl_w  = len(header)
        print()
        print(f"  {'═' * lbl_w}{sep}{'═' * lbl_w}")
        print(f"  {'TUA GRIGLIA':^{lbl_w}}{sep}{'GRIGLIA AVVERSARIO':^{lbl_w}}")
        print(f"  {'═' * lbl_w}{sep}{'═' * lbl_w}")
        print(f"{header}{sep}{header}")
        for i, letter in enumerate(self.LETTERS):
            my_row    = " ".join(f"{c:>2}" for c in self.my_grid[i])
            track_row = " ".join(f"{c:>2}" for c in self.tracking_grid[i])
            print(f" {letter}   {my_row}{sep} {letter}   {track_row}")
        print()
