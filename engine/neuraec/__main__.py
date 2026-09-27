import multiprocessing

from neuraec.cli import main

if __name__ == "__main__":
    # Nel motore congelato i processi ausiliari di multiprocessing rilanciano
    # this same executable: freeze_support catches them before the parser.
    multiprocessing.freeze_support()
    raise SystemExit(main())
