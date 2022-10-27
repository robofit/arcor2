import re
from argparse import ArgumentParser
from typing import NamedTuple


class Arguments(NamedTuple):

    start_paused: bool = False
    breakpoints: None | set[str] = None


def parse_args() -> Arguments:

    parser = ArgumentParser(prog="script.py")
    parser.add_argument("-p", "--start-paused", default=False, action="store_true")
    parser.add_argument("-b", "--breakpoints", default=None, type=str)

    args = parser.parse_args()

    return Arguments(args.start_paused, None if not args.breakpoints else set(re.findall(r"[\w']+", args.breakpoints)))
