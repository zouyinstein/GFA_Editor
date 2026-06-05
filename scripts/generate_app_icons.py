from __future__ import annotations

import math
from pathlib import Path
import struct
import zlib


ROOT_DIR = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT_DIR / "packaging" / "icons"
ICONSET_DIR = ICON_DIR / "GFA_Editor.iconset"
SVG_PATH = ICON_DIR / "GFA_Editor.svg"
ICNS_PATH = ICON_DIR / "GFA_Editor.icns"
ICO_PATH = ICON_DIR / "GFA_Editor.ico"


COLORS = {
    "bg_top": (248, 250, 247, 255),
    "bg_bottom": (229, 235, 231, 255),
    "grid": (207, 216, 209, 78),
    "edge": (142, 155, 143, 188),
    "ink": (24, 29, 26, 255),
    "highlight": (255, 255, 255, 150),
}

NODES = [
    (0.26, 0.25, 0.112, (56, 72, 244, 255)),
    (0.56, 0.31, 0.098, (205, 58, 194, 255)),
    (0.36, 0.57, 0.100, (10, 197, 139, 255)),
    (0.68, 0.62, 0.092, (75, 202, 74, 255)),
    (0.45, 0.80, 0.086, (165, 213, 52, 255)),
]

EDGES = [
    (0, 1),
    (0, 2),
    (1, 2),
    (2, 3),
    (3, 1),
    (2, 4),
    (4, 3),
]


def clamp(value: float, low: int = 0, high: int = 255) -> int:
    return max(low, min(high, int(round(value))))


def blend(dst: tuple[int, int, int, int], src: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    sr, sg, sb, sa = src
    dr, dg, db, da = dst
    sa_f = sa / 255
    da_f = da / 255
    out_a = sa_f + da_f * (1 - sa_f)
    if out_a <= 0:
        return (0, 0, 0, 0)
    return (
        clamp((sr * sa_f + dr * da_f * (1 - sa_f)) / out_a),
        clamp((sg * sa_f + dg * da_f * (1 - sa_f)) / out_a),
        clamp((sb * sa_f + db * da_f * (1 - sa_f)) / out_a),
        clamp(out_a * 255),
    )


class Canvas:
    def __init__(self, size: int, scale: int = 2) -> None:
        self.size = size
        self.scale = scale
        self.width = size * scale
        self.height = size * scale
        self.pixels = [(0, 0, 0, 0)] * (self.width * self.height)

    def put(self, x: int, y: int, color: tuple[int, int, int, int]) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            index = y * self.width + x
            self.pixels[index] = blend(self.pixels[index], color)

    def rounded_rect(self, x: float, y: float, w: float, h: float, r: float, color: tuple[int, int, int, int]) -> None:
        x *= self.width
        y *= self.height
        w *= self.width
        h *= self.height
        r *= self.width
        for py in range(max(0, int(y)), min(self.height, math.ceil(y + h))):
            for px in range(max(0, int(x)), min(self.width, math.ceil(x + w))):
                cx = min(max(px + 0.5, x + r), x + w - r)
                cy = min(max(py + 0.5, y + r), y + h - r)
                if math.hypot(px + 0.5 - cx, py + 0.5 - cy) <= r:
                    self.put(px, py, color)

    def circle(self, cx: float, cy: float, r: float, color: tuple[int, int, int, int]) -> None:
        cx *= self.width
        cy *= self.height
        r *= self.width
        for py in range(max(0, int(cy - r)), min(self.height, math.ceil(cy + r))):
            for px in range(max(0, int(cx - r)), min(self.width, math.ceil(cx + r))):
                if math.hypot(px + 0.5 - cx, py + 0.5 - cy) <= r:
                    self.put(px, py, color)

    def line(self, x1: float, y1: float, x2: float, y2: float, width: float, color: tuple[int, int, int, int]) -> None:
        x1 *= self.width
        y1 *= self.height
        x2 *= self.width
        y2 *= self.height
        width *= self.width
        dx = x2 - x1
        dy = y2 - y1
        length_sq = dx * dx + dy * dy
        pad = width + 2
        for py in range(max(0, int(min(y1, y2) - pad)), min(self.height, math.ceil(max(y1, y2) + pad))):
            for px in range(max(0, int(min(x1, x2) - pad)), min(self.width, math.ceil(max(x1, x2) + pad))):
                if length_sq <= 0:
                    distance = math.hypot(px - x1, py - y1)
                else:
                    t = max(0, min(1, ((px + 0.5 - x1) * dx + (py + 0.5 - y1) * dy) / length_sq))
                    qx = x1 + dx * t
                    qy = y1 + dy * t
                    distance = math.hypot(px + 0.5 - qx, py + 0.5 - qy)
                if distance <= width / 2:
                    self.put(px, py, color)

    def triangle(self, points: list[tuple[float, float]], color: tuple[int, int, int, int]) -> None:
        scaled = [(x * self.width, y * self.height) for x, y in points]
        min_x = max(0, int(min(x for x, _ in scaled)))
        max_x = min(self.width, math.ceil(max(x for x, _ in scaled)))
        min_y = max(0, int(min(y for _, y in scaled)))
        max_y = min(self.height, math.ceil(max(y for _, y in scaled)))

        def sign(p, a, b):
            return (p[0] - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (p[1] - b[1])

        a, b, c = scaled
        for py in range(min_y, max_y):
            for px in range(min_x, max_x):
                p = (px + 0.5, py + 0.5)
                d1 = sign(p, a, b)
                d2 = sign(p, b, c)
                d3 = sign(p, c, a)
                has_neg = d1 < 0 or d2 < 0 or d3 < 0
                has_pos = d1 > 0 or d2 > 0 or d3 > 0
                if not (has_neg and has_pos):
                    self.put(px, py, color)

    def downsample(self) -> list[tuple[int, int, int, int]]:
        result = []
        s = self.scale
        for y in range(self.size):
            for x in range(self.size):
                channels = [0, 0, 0, 0]
                for yy in range(s):
                    for xx in range(s):
                        pixel = self.pixels[(y * s + yy) * self.width + (x * s + xx)]
                        for i in range(4):
                            channels[i] += pixel[i]
                div = s * s
                result.append(tuple(clamp(value / div) for value in channels))  # type: ignore[arg-type]
        return result


def write_png(path: Path, size: int, pixels: list[tuple[int, int, int, int]]) -> None:
    raw = bytearray()
    for y in range(size):
        raw.append(0)
        for x in range(size):
            raw.extend(pixels[y * size + x])

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    png = bytearray(b"\x89PNG\r\n\x1a\n")
    png.extend(chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)))
    png.extend(chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
    png.extend(chunk(b"IEND", b""))
    path.write_bytes(bytes(png))


def draw_icon(size: int) -> list[tuple[int, int, int, int]]:
    scale = 4 if size <= 128 else 2 if size <= 512 else 1
    c = Canvas(size, scale=scale)
    # background shadow
    c.rounded_rect(0.075, 0.09, 0.85, 0.85, 0.21, (0, 0, 0, 24))
    c.rounded_rect(0.055, 0.045, 0.89, 0.89, 0.22, COLORS["bg_top"])
    for row in range(c.height):
        t = row / max(c.height - 1, 1)
        color = tuple(clamp(COLORS["bg_top"][i] * (1 - t) + COLORS["bg_bottom"][i] * t) for i in range(4))
        for col in range(c.width):
            if c.pixels[row * c.width + col][3]:
                c.pixels[row * c.width + col] = color  # type: ignore[assignment]

    # subtle grid
    for offset in [0.20, 0.34, 0.48, 0.62, 0.76]:
        c.line(0.12, offset, 0.88, offset, 0.004, COLORS["grid"])
        c.line(offset, 0.12, offset, 0.88, 0.004, COLORS["grid"])

    # edges and arrowheads
    for source_idx, target_idx in EDGES:
        sx, sy, sr, _ = NODES[source_idx]
        tx, ty, tr, _ = NODES[target_idx]
        dx = tx - sx
        dy = ty - sy
        length = max(math.hypot(dx, dy), 0.001)
        ux = dx / length
        uy = dy / length
        start = (sx + ux * sr * 0.78, sy + uy * sr * 0.78)
        end = (tx - ux * tr * 0.82, ty - uy * tr * 0.82)
        c.line(start[0], start[1], end[0], end[1], 0.026, COLORS["edge"])
        angle = math.atan2(uy, ux)
        arrow = 0.038
        side = 0.026
        tip = end
        left = (tip[0] - math.cos(angle - 0.55) * arrow, tip[1] - math.sin(angle - 0.55) * arrow)
        right = (tip[0] - math.cos(angle + 0.55) * arrow, tip[1] - math.sin(angle + 0.55) * arrow)
        c.triangle([tip, left, right], COLORS["edge"])

    # nodes
    for x, y, r, color in NODES:
        c.circle(x, y + 0.012, r * 1.04, (0, 0, 0, 42))
        c.circle(x, y, r, (21, 24, 22, 235))
        c.circle(x, y, r * 0.89, color)
        c.circle(x - r * 0.24, y - r * 0.28, r * 0.22, COLORS["highlight"])

    return c.downsample()


def write_svg() -> None:
    SVG_PATH.write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024">
  <rect x="56" y="48" width="912" height="912" rx="224" fill="#f7faf7"/>
  <path d="M56 520h912M56 660h912M56 800h912M224 48v912M384 48v912M544 48v912M704 48v912M864 48v912" stroke="#cfd8d1" stroke-opacity=".32" stroke-width="4"/>
  <g stroke="#8e9b8f" stroke-width="28" stroke-linecap="round" stroke-opacity=".74" fill="none">
    <path d="M266 256L553 317"/>
    <path d="M266 256L368 584"/>
    <path d="M553 317L368 584"/>
    <path d="M368 584L694 635"/>
    <path d="M694 635L553 317"/>
    <path d="M368 584L461 819"/>
    <path d="M461 819L694 635"/>
  </g>
  <g stroke="#181d1a" stroke-width="18">
    <circle cx="266" cy="256" r="102" fill="#3848f4"/>
    <circle cx="553" cy="317" r="90" fill="#cd3ac2"/>
    <circle cx="368" cy="584" r="92" fill="#0ac58b"/>
    <circle cx="694" cy="635" r="84" fill="#4bca4a"/>
    <circle cx="461" cy="819" r="78" fill="#a5d534"/>
  </g>
</svg>
""",
        encoding="utf-8",
    )


def write_ico(png_paths: list[Path]) -> None:
    entries = []
    data = []
    offset = 6 + 16 * len(png_paths)
    for path in png_paths:
        size = int(path.stem.split("_")[-1])
        png = path.read_bytes()
        width_byte = 0 if size >= 256 else size
        entries.append(struct.pack("<BBBBHHII", width_byte, width_byte, 0, 0, 1, 32, len(png), offset))
        data.append(png)
        offset += len(png)
    ICO_PATH.write_bytes(struct.pack("<HHH", 0, 1, len(entries)) + b"".join(entries) + b"".join(data))


def write_icns() -> None:
    icon_chunks = [
        ("icp4", ICONSET_DIR / "icon_16x16.png"),
        ("icp5", ICONSET_DIR / "icon_32x32.png"),
        ("icp6", ICONSET_DIR / "icon_32x32@2x.png"),
        ("ic07", ICONSET_DIR / "icon_128x128.png"),
        ("ic08", ICONSET_DIR / "icon_256x256.png"),
        ("ic09", ICONSET_DIR / "icon_512x512.png"),
        ("ic10", ICONSET_DIR / "icon_512x512@2x.png"),
    ]
    body = bytearray()
    for kind, path in icon_chunks:
        data = path.read_bytes()
        body.extend(kind.encode("ascii"))
        body.extend(struct.pack(">I", len(data) + 8))
        body.extend(data)
    ICNS_PATH.write_bytes(b"icns" + struct.pack(">I", len(body) + 8) + bytes(body))


def main() -> int:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    ICONSET_DIR.mkdir(parents=True, exist_ok=True)
    write_svg()

    iconset_specs = [
        ("icon_16x16.png", 16),
        ("icon_16x16@2x.png", 32),
        ("icon_32x32.png", 32),
        ("icon_32x32@2x.png", 64),
        ("icon_128x128.png", 128),
        ("icon_128x128@2x.png", 256),
        ("icon_256x256.png", 256),
        ("icon_256x256@2x.png", 512),
        ("icon_512x512.png", 512),
        ("icon_512x512@2x.png", 1024),
    ]
    for filename, size in iconset_specs:
        write_png(ICONSET_DIR / filename, size, draw_icon(size))

    ico_pngs = []
    for size in [16, 32, 48, 64, 128, 256]:
        path = ICON_DIR / f"ico_{size}.png"
        write_png(path, size, draw_icon(size))
        ico_pngs.append(path)
    write_ico(ico_pngs)
    write_icns()

    print(f"Wrote {SVG_PATH}")
    print(f"Wrote {ICNS_PATH}")
    print(f"Wrote {ICO_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
