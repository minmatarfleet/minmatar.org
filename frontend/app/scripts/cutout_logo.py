#!/usr/bin/env python3
"""Remove a near-black background from a logo and save a transparent PNG.

Flood-fills transparency inward from the image edges, so only the background
connected to the border is removed — black *inside* the logo is preserved.

Usage:
    python3 scripts/cutout_logo.py <source> <dest.png> [--threshold 60] [--trim]

Example (from frontend/app):
    python3 scripts/cutout_logo.py ~/Downloads/slide.png \
        public/images/warzone/logos/slide-on-contact.png --trim
"""
import argparse
from collections import deque
from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("dest")
    parser.add_argument("--threshold", type=int, default=60,
                        help="max per-channel brightness treated as background (0-255)")
    parser.add_argument("--trim", action="store_true", help="crop to the remaining opaque bounds")
    args = parser.parse_args()

    img = Image.open(args.source).convert("RGBA")
    width, height = img.size
    px = img.load()

    def is_bg(x: int, y: int) -> bool:
        r, g, b, a = px[x, y]
        return a > 0 and r <= args.threshold and g <= args.threshold and b <= args.threshold

    seen = [[False] * width for _ in range(height)]
    queue: deque[tuple[int, int]] = deque()
    for x in range(width):
        for y in (0, height - 1):
            queue.append((x, y))
    for y in range(height):
        for x in (0, width - 1):
            queue.append((x, y))

    cleared = 0
    while queue:
        x, y = queue.popleft()
        if x < 0 or y < 0 or x >= width or y >= height or seen[y][x]:
            continue
        seen[y][x] = True
        if not is_bg(x, y):
            continue
        r, g, b, _ = px[x, y]
        px[x, y] = (r, g, b, 0)
        cleared += 1
        queue.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

    if args.trim:
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)

    img.save(args.dest)
    print(f"Cleared {cleared} background pixels -> {args.dest} ({img.size[0]}x{img.size[1]})")


if __name__ == "__main__":
    main()
