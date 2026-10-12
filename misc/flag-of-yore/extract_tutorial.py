#!/usr/bin/env python3
"""Extract the leaked development screenshot from the game's tutorial pack."""

import argparse
from pathlib import Path

from PIL import Image


WIDTH, HEIGHT = 720, 640
HEADER_SIZE = 24
IMAGE_SIZE = WIDTH * HEIGHT * 4  # RGBA
DEV_SCREENSHOT_INDEX = 4


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack", type=Path, help="downloaded tutorial.pak")
    parser.add_argument("-o", "--output", type=Path, default=Path("dev_tutorial.png"))
    args = parser.parse_args()

    data = args.pack.read_bytes()
    offset = HEADER_SIZE + DEV_SCREENSHOT_INDEX * IMAGE_SIZE
    pixels = data[offset:offset + IMAGE_SIZE]
    if len(pixels) != IMAGE_SIZE:
        parser.error("tutorial pack is too short for the development screenshot")

    Image.frombytes("RGBA", (WIDTH, HEIGHT), pixels).save(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
