class Ship:
    def __init__(self, name: str, size: int):
        self.name  = name
        self.size  = size
        self.cells: list[tuple] = []
        self.hits:  set[tuple]  = set()

    def place(self, cells: list):
        self.cells = list(cells)

    def occupies(self, row: int, col: int) -> bool:
        return (row, col) in self.cells

    def hit(self, row: int, col: int):
        self.hits.add((row, col))

    def is_sunk(self) -> bool:
        return len(self.hits) >= len(self.cells)

    def is_damaged(self) -> bool:
        return len(self.hits) > 0 and not self.is_sunk()

    def __repr__(self):
        stato = "affondata" if self.is_sunk() else ("danneggiata" if self.is_damaged() else "intatta")
        return f"{self.name}(size={self.size}, {stato})"
