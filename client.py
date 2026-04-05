"""
client.py — Entry point.

Uso:
    python client.py          → GUI (default)
    python client.py --gui    → GUI
    python client.py --term   → Terminale
"""

import sys


def main():
    mode = "gui"
    if "--term" in sys.argv or "--terminal" in sys.argv:
        mode = "terminal"
    elif "--gui" in sys.argv:
        mode = "gui"

    if mode == "terminal":
        from client_terminal import run_terminal
        print("╔══════════════════════════════════════════╗")
        print("║   BATTAGLIA NAVALE  ·  CLIENT  (Pyro5)   ║")
        print("╚══════════════════════════════════════════╝")
        name = input("  Il tuo nome: ").strip() or "Giocatore"
        try:
            run_terminal(name)
        except KeyboardInterrupt:
            print("\n[CLIENT] Disconnesso.")
    else:
        from client_gui import BattleshipGUI
        app = BattleshipGUI()
        app.mainloop()


if __name__ == "__main__":
    main()
