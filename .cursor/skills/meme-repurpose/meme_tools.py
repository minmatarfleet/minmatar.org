#!/usr/bin/env python3
"""Tools for repurposing a short-form meme video: find scene cuts, make
keyframe sheets, track an overlay along keyframes, cut out EVE ship renders,
render a fleet-in-warp intro, and assemble the finished vertical video.

Needs ffmpeg, curl, numpy and Pillow. Run it with python3; it reads and writes
only the paths you give it. See SKILL.md in this folder for the workflow.
"""
import argparse
import json
import math
import os
import random
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

IMAGE_SERVER = "https://images.evetech.net/types/{type_id}/render?size=512"


def run(cmd):
    subprocess.run(cmd, check=True)


def font_file(pattern):
    out = subprocess.run(
        ["fc-match", "-f", "%{file}", pattern], capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


def load_template(path):
    return json.loads(Path(path).read_text())


def extract_frames(video, out_dir, start=0.0, crop=None, count=None, fps=None):
    """Write 1-based PNG frames (0001.png ...) from a video."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    filters = []
    if fps:
        filters.append(f"fps={fps}")
    if crop:
        x, y, w, h = crop
        filters.append(f"crop={w}:{h}:{x}:{y}")
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", str(start), "-i", str(video)]
    if filters:
        cmd += ["-vf", ",".join(filters)]
    if count:
        cmd += ["-frames:v", str(count)]
    run(cmd + [str(out_dir / "%04d.png")])
    return sorted(out_dir.glob("*.png"))


# --- cuts -------------------------------------------------------------------

def cmd_cuts(a):
    """Print frames where the picture changes sharply: scene cuts.

    ffmpeg's scene filter misses cuts between similar painted backgrounds, so
    this compares mean absolute difference of small greyscale frames instead.
    """
    with tempfile.TemporaryDirectory() as tmp:
        frames = extract_frames(a.video, tmp, start=a.start, crop=a.crop)
        prev = None
        for i, f in enumerate(frames, 1):
            img = Image.open(f).convert("L").resize((108, 92))
            cur = np.asarray(img).astype(float)
            if prev is not None:
                diff = np.abs(cur - prev).mean()
                if diff > a.threshold:
                    print(f"frame {i}  diff {diff:.1f}  mean {cur.mean():.1f}")
            prev = cur
        print(f"{len(frames)} frames")


# --- sheet ------------------------------------------------------------------

def cmd_sheet(a):
    """Gridded, frame-numbered contact sheets for reading positions by eye."""
    with tempfile.TemporaryDirectory() as tmp:
        frames = extract_frames(a.video, tmp, start=a.start, crop=a.crop)
        bold = font_file("Inter:bold")
        big = ImageFont.truetype(bold, 28)
        small = ImageFont.truetype(bold, 14)
        picks = sorted(set(list(range(1, len(frames) + 1, a.every)) + a.include))
        tiles = []
        for n in picks:
            if n > len(frames):
                continue
            im = Image.open(frames[n - 1]).convert("RGB")
            w, h = im.size
            dr = ImageDraw.Draw(im)
            for x in range(0, w, 100):
                dr.line([(x, 0), (x, h)], fill=(255, 255, 255), width=1)
            for y in range(0, h, 100):
                dr.line([(0, y), (w, y)], fill=(255, 255, 255), width=1)
            im = im.resize((w // 2, h // 2))
            dr = ImageDraw.Draw(im)
            for x in range(100, w, 100):
                dr.text((x / 2 + 2, 2), str(x), font=small, fill=(255, 255, 0))
            for y in range(100, h, 100):
                dr.text((2, y / 2 + 2), str(y), font=small, fill=(255, 255, 0))
            dr.rectangle([0, h // 2 - 32, 110, h // 2], fill=(0, 0, 0))
            dr.text((4, h // 2 - 30), f"f{n}", font=big, fill=(0, 255, 255))
            tiles.append(im)
        cols, rows = 4, 3
        tw, th = tiles[0].size
        for s in range(0, len(tiles), cols * rows):
            sheet = Image.new("RGB", (tw * cols, th * rows))
            for i, t in enumerate(tiles[s:s + cols * rows]):
                sheet.paste(t, ((i % cols) * tw, (i // cols) * th))
            out = f"{a.out}{s // (cols * rows)}.png"
            sheet.save(out)
            print(out)


# --- track ------------------------------------------------------------------

def track_position(keyframes, frame):
    """Linear interpolation inside the scene that holds `frame`, else None."""
    for scene in keyframes:
        first, last = scene[0][0], scene[-1][0]
        if not (first <= frame <= last):
            continue
        for (f0, *p0), (f1, *p1) in zip(scene, scene[1:]):
            if f0 <= frame <= f1:
                t = (frame - f0) / max(1, f1 - f0)
                return [p0[i] + (p1[i] - p0[i]) * t for i in range(len(p0))]
        return scene[-1][1:]
    return None


def cmd_track(a):
    """Composite an overlay image onto the punchline clip along a template track."""
    tpl = load_template(a.template)
    keyframes = tpl["tracks"][a.track]["keyframes"]
    p = tpl["punchline"]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    overlay = Image.open(a.overlay).convert("RGBA")
    with tempfile.TemporaryDirectory() as tmp:
        frames = extract_frames(
            a.source, tmp, start=tpl["cut_seconds"], crop=p["clip_box"], count=p["frames"]
        )
        for n, f in enumerate(frames, 1):
            im = Image.open(f).convert("RGBA")
            pos = track_position(keyframes, n)
            if pos:
                x, y, size = pos
                size = int(round(size * a.scale))
                badge = overlay.resize((size, int(overlay.height * size / overlay.width)), Image.LANCZOS)
                im.alpha_composite(badge, (int(x - badge.width / 2), int(y - badge.height / 2)))
            im.convert("RGB").save(out / f"{n:04d}.png")
    print(f"{len(frames)} frames -> {out}")


# --- cutout -----------------------------------------------------------------

def ship_mask(im):
    """Separate a ship from the image server's nebula background.

    Backgrounds are red/magenta haze: dark maroon at the top, pale pink fog at
    the bottom. Dark pixels count as background only when strongly red (ship
    shadows are near-neutral); brighter pixels are background when they are
    pink (red over green, blue at least green) or pale and not green.
    """
    a = np.asarray(im.filter(ImageFilter.GaussianBlur(1.2))).astype(float)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    lum = 0.3 * r + 0.59 * g + 0.11 * b
    bg = np.where(
        lum < 70,
        r > g * 1.6,
        ((r > g * 1.2) & (b >= g * 0.9)) | (r > g * 1.8)
        | ((lum > 165) & (b >= g * 0.97) & (r >= g * 0.95)),
    )
    m = Image.fromarray(np.where(bg, 0, 255).astype(np.uint8))
    m = m.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(11)).filter(ImageFilter.MinFilter(9))
    # .copy(): an image made by fromarray can share numpy's buffer, and
    # floodfill then silently does nothing.
    m = m.point(lambda v: 255 if v > 127 else 0).copy()
    arr = np.asarray(m)
    best = None
    for y in range(32, arr.shape[0], 24):
        for x in range(32, arr.shape[1], 24):
            if arr[y, x] != 255:
                continue
            t = m.copy()
            ImageDraw.floodfill(t, (x, y), 128, thresh=0)
            k = np.asarray(t) == 128
            if best is None or k.sum() > best.sum():
                best = k
    h = Image.fromarray(np.where(best, 255, 0).astype(np.uint8)).copy()
    ImageDraw.floodfill(h, (0, 0), 60, thresh=0)  # everything not reached is ship or a hole in it
    return Image.fromarray(np.where(np.asarray(h) != 60, 255, 0).astype(np.uint8))


def cmd_cutout(a):
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "render.jpg"
        run(["curl", "-sSf", "-o", str(src), IMAGE_SERVER.format(type_id=a.type_id)])
        im = Image.open(src).convert("RGB")
    mask = ship_mask(im)
    gain, lift = (1.9, 25) if a.style == "toy" else (1.25, 5)
    rgb = np.clip(np.asarray(im).astype(float) * gain + lift, 0, 255).astype(np.uint8)
    ship = Image.fromarray(rgb).convert("RGBA")
    ship.putalpha(mask.filter(ImageFilter.GaussianBlur(0.8)))
    if a.style == "toy":
        # cartoon look: black line inside a cream (fleet colour) outer line
        base = Image.new("RGBA", im.size, (241, 217, 160, 255))
        base.putalpha(mask.filter(ImageFilter.MaxFilter(17)).filter(ImageFilter.GaussianBlur(1)))
        black = Image.new("RGBA", im.size, (15, 10, 8, 255))
        black.putalpha(mask.filter(ImageFilter.MaxFilter(7)))
        base.alpha_composite(black)
        base.alpha_composite(ship)
        ship = base
    # Renders show the nose at the lower left. rotate(-52) levels the ship,
    # nose left, still upright; rotate(128) would point it right but upside down.
    ship = ship.rotate(a.rotate, resample=Image.BICUBIC, expand=True)
    if a.mirror:
        ship = ship.transpose(Image.FLIP_LEFT_RIGHT)
    ship = ship.crop(ship.getbbox())
    ship.save(out)
    print(f"{out} {ship.size}")


# --- warp intro -------------------------------------------------------------

def cmd_warp_intro(a):
    """A fleet in warp: dark space, a rust-red glow, streaks, bobbing hulls.

    --ship takes path,x,y,width,depth (depth 0..1: far ships are dimmer,
    softer and move less). Ships face left; streaks run left to right.
    """
    W, H = a.size
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    random.seed(7)
    yy, xx = np.mgrid[0:H, 0:W].astype(float)

    def glow(cx, cy, rad, col, k):
        g = np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * rad ** 2)))[..., None]
        return g * np.array(col) * k

    bg = glow(W * 0.28, H * 0.36, 520, (150, 45, 25), 0.38)
    bg += glow(W * 0.79, H * 0.73, 600, (110, 50, 25), 0.28)
    bg += glow(W * 0.56, H * 0.52, 900, (15, 20, 45), 0.8)
    bg = np.clip(bg + 3 + np.random.default_rng(3).normal(0, 3, (H, W, 1)), 0, 255)
    background = Image.fromarray(bg.astype(np.uint8)).convert("RGBA")

    streaks = [dict(
        y=random.uniform(H * 0.13, H * 0.91), x=random.uniform(-400, W + 400),
        length=random.uniform(120, 700), speed=random.uniform(90, 220),
        width=random.choice([1, 1, 2, 2, 3]), alpha=random.randint(70, 220),
        col=random.choice([(200, 225, 255), (160, 200, 255), (255, 235, 210), (255, 255, 255)]),
    ) for _ in range(260)]

    fleet = []
    for i, spec in enumerate(a.ship):
        path, x, y, w, depth = spec.split(",")
        im = Image.open(path).convert("RGBA")
        depth = float(depth)
        if depth < 1:
            alpha = im.getchannel("A")
            im = ImageEnhance.Brightness(im.convert("RGB")).enhance(0.55 + 0.45 * depth).convert("RGBA")
            im.putalpha(alpha)
            im = im.filter(ImageFilter.GaussianBlur((1 - depth) * 1.5))
        fleet.append((im, float(x), float(y), float(w), i * 1.3, depth))
    fleet.sort(key=lambda s: s[5])

    for f in range(a.frames):
        t = f / a.fps
        frame = background.copy()
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(layer)
        for s in streaks:
            x = (s["x"] + s["speed"] * f) % (W + 1100) - 500
            dr.line([(x, s["y"]), (x + s["length"], s["y"])], fill=s["col"] + (s["alpha"],), width=s["width"])
        frame.alpha_composite(layer.filter(ImageFilter.GaussianBlur(1.2)))
        frame.alpha_composite(layer)
        zoom = 1.0 + 0.06 * t / max(0.1, a.frames / a.fps)
        sx, sy = math.sin(f * 1.9) * 3, math.cos(f * 2.3) * 3
        for im, cx, cy, w, ph, depth in fleet:
            w2 = int(w * zoom)
            h2 = int(im.height * w2 / im.width)
            ship = im.resize((w2, h2), Image.LANCZOS)
            bob = math.sin(t * 2.2 + ph) * 10 * depth
            x = cx + math.sin(t * 0.9 + ph) * 12 * depth
            ex, ey, r = x + w2 * 0.47 + sx, cy + h2 * 0.05 + bob + sy, w2 * 0.07
            g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(g).ellipse([ex - r * 0.5, ey - r, ex + r * 2.5, ey + r], fill=(255, 150, 70, int(150 * depth)))
            frame.alpha_composite(g.filter(ImageFilter.GaussianBlur(r * 0.6)))
            frame.alpha_composite(ship, (int(x - w2 / 2 + sx), int(cy - h2 / 2 + bob + sy)))
        frame.convert("RGB").save(out / f"{f + 1:04d}.png")
    print(f"{a.frames} frames -> {out}")


# --- assemble ---------------------------------------------------------------

def escape(text):
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’")


def cmd_assemble(a):
    """Setup (frames dir or video) + punchline (tracked frames) + source audio."""
    tpl = load_template(a.template)
    W, H = tpl["size"]
    fps, cut = tpl["fps"], tpl["cut_seconds"]
    s, p = tpl["setup"], tpl["punchline"]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cap = tmp / "setup.txt"
        cap.write_text(a.setup_text.replace("\\n", "\n"))
        setup_font = font_file(s["caption_font"])
        caption = (f"drawtext=fontfile='{setup_font}':textfile='{cap}':fontsize={s['caption_size']}:"
                   f"fontcolor=white:line_spacing=8:text_align=C:shadowcolor=black@0.7:"
                   f"shadowx=3:shadowy=3:x=(w-tw)/2:y={s['caption_y']}")
        if Path(a.setup).is_dir():
            src = ["-framerate", str(fps), "-i", str(Path(a.setup) / "%04d.png")]
            vf = caption
        else:
            src = ["-i", a.setup]
            vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps},{caption}"
        run(["ffmpeg", "-v", "error", "-y", *src, "-t", str(cut), "-an", "-vf", vf,
             "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(tmp / "a.mp4")])

        label_font = font_file(p["label_font"])
        step_font = font_file(p["step_font"])
        x, y, w, h = p["clip_box"]
        filters = [f"pad={W}:{H}:{x}:{y}:black",
                   f"drawtext=fontfile='{label_font}':text='{escape(a.label)}':fontsize={p['label_size']}:"
                   f"fontcolor=white:x=(w-tw)/2:y={p['label_baseline']}-th"]
        for step in a.step:
            span, text = step.split(":", 1)
            first, last = span.split("-")
            enable = f"between(n,{int(first) - 1},{int(last) - 1})"
            filters.append(f"drawtext=fontfile='{step_font}':text='{escape(text)}':fontsize={p['step_size']}:"
                           f"fontcolor=white:x=(w-tw)/2:y={p['step_y']}:enable='{enable}'")
        run(["ffmpeg", "-v", "error", "-y", "-framerate", str(fps), "-i", str(Path(a.punchline) / "%04d.png"),
             "-vf", ",".join(filters), "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(tmp / "b.mp4")])

        run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp / "a.mp4"), "-i", str(tmp / "b.mp4"), "-i", a.source,
             "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]", "-map", "2:a", "-shortest",
             "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", a.out])
    print(a.out)


def box(text):
    return [int(v) for v in text.split(":")]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("cuts", help="print scene-cut frame numbers")
    c.add_argument("video")
    c.add_argument("--start", type=float, default=0.0, help="seconds to skip first")
    c.add_argument("--crop", type=box, help="x:y:w:h")
    c.add_argument("--threshold", type=float, default=18.0)
    c.set_defaults(fn=cmd_cuts)

    c = sub.add_parser("sheet", help="gridded keyframe sheets")
    c.add_argument("video")
    c.add_argument("--start", type=float, default=0.0)
    c.add_argument("--crop", type=box, help="x:y:w:h")
    c.add_argument("--every", type=int, default=4)
    c.add_argument("--include", type=int, nargs="*", default=[], help="extra frames, e.g. scene starts")
    c.add_argument("--out", required=True, help="output prefix; writes <prefix>0.png, <prefix>1.png ...")
    c.set_defaults(fn=cmd_sheet)

    c = sub.add_parser("track", help="composite an overlay along a template track")
    c.add_argument("--template", required=True)
    c.add_argument("--track", required=True)
    c.add_argument("--source", required=True, help="the original reel")
    c.add_argument("--overlay", required=True, help="PNG with transparency")
    c.add_argument("--scale", type=float, default=1.0, help="multiply the keyframe sizes")
    c.add_argument("--out", required=True, help="output frames directory")
    c.set_defaults(fn=cmd_track)

    c = sub.add_parser("cutout", help="cut an EVE ship render out of its background")
    c.add_argument("--type-id", required=True, type=int)
    c.add_argument("--style", choices=["plain", "toy"], default="plain")
    c.add_argument("--rotate", type=float, default=-52.0)
    c.add_argument("--mirror", action="store_true", help="nose right (a mirror image of the hull)")
    c.add_argument("--out", required=True)
    c.set_defaults(fn=cmd_cutout)

    c = sub.add_parser("warp-intro", help="render a fleet-in-warp intro")
    c.add_argument("--ship", action="append", required=True, help="path,x,y,width,depth")
    c.add_argument("--frames", type=int, default=103)
    c.add_argument("--fps", type=int, default=30)
    c.add_argument("--size", type=int, nargs=2, default=[1080, 1920])
    c.add_argument("--out", required=True)
    c.set_defaults(fn=cmd_warp_intro)

    c = sub.add_parser("assemble", help="build the finished video")
    c.add_argument("--template", required=True)
    c.add_argument("--source", required=True, help="the original reel (audio)")
    c.add_argument("--setup", required=True, help="frames directory or a video clip")
    c.add_argument("--setup-text", required=True, help=r"use \n for a line break")
    c.add_argument("--punchline", required=True, help="frames directory from `track`")
    c.add_argument("--label", required=True, help="e.g. 'me and Minmatar Fleet:'")
    c.add_argument("--step", action="append", default=[], help="first-last:text, punchline frames (1-based)")
    c.add_argument("--out", required=True)
    c.set_defaults(fn=cmd_assemble)

    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
