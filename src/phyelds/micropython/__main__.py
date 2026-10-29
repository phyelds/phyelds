"""Command line: ``python -m phyelds.micropython program.py [more.py ...] -o dist``."""
import argparse
from pathlib import Path

from phyelds.micropython.build import build


def main() -> None:
    """Build the MicroPython bundle of the programs given on the command line."""
    parser = argparse.ArgumentParser(
        prog="python -m phyelds.micropython",
        description="Write phyelds and the given programs, rewritten for MicroPython.",
    )
    parser.add_argument("sources", nargs="*", type=Path, help="modules of the program")
    parser.add_argument("-o", "--out", type=Path, default=Path("dist"), help="output directory")
    parser.add_argument(
        "--include", action="append", default=[], metavar="MODULE",
        help="a module of phyelds to write although the program imports it by a computed name",
    )
    arguments = parser.parse_args()
    build(arguments.sources, arguments.out, include=arguments.include)


if __name__ == "__main__":
    main()
