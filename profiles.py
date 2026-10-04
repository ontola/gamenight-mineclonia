"""GameNight profile -> Mineclonia appearance, with no image/runtime dependency.

Avatar v1 and legacy decoding follows gamenight-protocol/src/avatar.rs.
The Python adapter has no Rust SDK; keep the compatibility tests with this port.
Images are small, session-specific embedded PNGs (never paths or remote URLs).
"""

import base64
import json
import math
import re
import struct
import unicodedata
import zlib

COLORS = ("#4daf7c", "#e36c76", "#648cdd", "#d7ad43")
SKIN = "#efc39a"


def rgb(value):
    if not isinstance(value, str):
        return None
    value = value.strip().lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", value):
        return None
    return tuple(bytes.fromhex(value))


def avatar(data):
    if not isinstance(data, str) or len(data) > 800000:
        return None
    try:
        value = json.loads(data)
        if isinstance(value, dict):
            if type(value.get("v")) is not int or value["v"] != 1:
                return None
            w, h, cells = value.get("w"), value.get("h"), value.get("px")
        elif isinstance(value, list) and all(isinstance(v, str) for v in value):
            w = h = math.isqrt(len(value))
            cells = [None if v.lower() == "#0f172a" else v for v in value]
        else:
            return None
        if (
            type(w) is not int
            or type(h) is not int
            or not 1 <= w <= 256
            or not 1 <= h <= 256
        ):
            return None
        if not isinstance(cells, list) or len(cells) != w * h:
            return None
        if any(v is not None and not isinstance(v, str) for v in cells):
            return None
        pixels = [rgb(v) for v in cells]
        return (w, h, pixels) if any(pixels) else None
    except (ValueError, TypeError, RecursionError):
        return None


def face_pixels(data, skin):
    # Same 48px head space as Avatar::head_layout, including old studio sizes.
    pixels = [None] * (48 * 48)
    for y in range(48):
        for x in range(48):
            if (x + 0.5 - 24) ** 2 + (y + 0.5 - 28) ** 2 <= 12**2:
                pixels[y * 48 + x] = skin
    art = avatar(data)
    if art:
        w, h, source = art

        def offset(size, small):
            return small if size == 32 else small + 8 if size == 16 else (48 - size) / 2

        ox, oy = offset(w, 14), offset(h, 15)
        for y in range(48):
            for x in range(48):
                sx, sy = math.floor(x - ox), math.floor(y - oy)
                if 0 <= sx < w and 0 <= sy < h and source[sy * w + sx]:
                    pixels[y * 48 + x] = source[sy * w + sx]
    else:
        for x in (20, 29):
            for y in range(24, 28):
                for dx in range(3):
                    pixels[y * 48 + x + dx] = (26, 26, 26)
        for x in range(23, 31):
            pixels[33 * 48 + x] = (26, 26, 26)
    return pixels


def png(w, h, pixels):
    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data))
        )

    raw = b"".join(
        b"\0"
        + b"".join(
            bytes((*p, 255)) if p else b"\0\0\0\0" for p in pixels[y * w : (y + 1) * w]
        )
        for y in range(h)
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def texture(w, h, pixels):
    return "[png:" + base64.b64encode(png(w, h, pixels)).decode("ascii")


def skin_pixels(face, skin, color):
    # Mineclonia 64x32 UV layout (both limbs share UVs), six pixels per texel.
    size, scale = 384, 6
    out = [None] * (size * size // 2)

    def rect(x, y, w, h, c):
        for row in range(y * scale, (y + h) * scale):
            out[row * size + x * scale : row * size + (x + w) * scale] = [c] * (
                w * scale
            )

    def shade(c, f):
        return tuple(round(v * f) for v in c)

    rect(0, 0, 32, 16, skin)
    hair = next((p for p in face[16 * 48 : 17 * 48] if p and p != skin), skin)
    rect(8, 0, 8, 8, hair)
    rect(24, 8, 8, 6, hair)
    rect(0, 8, 8, 4, hair)
    rect(16, 8, 8, 4, hair)
    # Torso and short sleeves; leave overlay/armor layers transparent.
    rect(16, 16, 24, 16, color)
    rect(20, 20, 8, 2, shade(color, 0.82))
    rect(23, 20, 2, 1, skin)
    for x, y in ((40, 16),):
        rect(x, y, 16, 16, color)
        rect(x, y + 9, 16, 7, skin)
    for x, y in ((0, 16),):
        rect(x, y, 16, 16, (42, 51, 67))
        rect(x, y + 13, 16, 3, (28, 31, 39))
    # Face artwork is anchored to the shared head centre, not its painted bounds.
    # Fit the 32px head region to the cube; the badge retains all headwear.
    for y in range(48):
        for x in range(48):
            sx, sy = 8 + x * 32 // 48, 8 + y * 32 // 48
            if face[sy * 48 + sx]:
                out[(8 * scale + y) * size + 8 * scale + x] = face[sy * 48 + sx]
    return out


def appearances(seats, players, accounts=None):
    by_id = {
        p.get("id"): p
        for p in players
        if isinstance(p, dict) and isinstance(p.get("id"), str)
    }
    result = {}
    for seat in seats:
        i = seat["index"]
        occupant = seat.get("occupant", {})
        p = (
            by_id.get(occupant.get("player_id"), {})
            if occupant.get("kind") == "local"
            else {}
        )
        name = p.get("name")
        name = (
            "".join(
                c for c in name if not unicodedata.category(c).startswith("C")
            ).strip()
            if isinstance(name, str)
            else ""
        )
        name = (name[:31] + "…") if len(name) > 32 else name
        skin = rgb(p.get("skin_color")) or rgb(SKIN)
        color = rgb(p.get("color")) or rgb(COLORS[i])
        face = face_pixels(p.get("avatar"), skin)
        account = accounts[i] if accounts is not None else f"Couch{i + 1}"
        result[account] = dict(
            seat=i + 1,
            name=name or f"Player {i + 1}",
            color="#" + bytes(color).hex(),
            face=texture(48, 48, face),
            skin=texture(384, 192, skin_pixels(face, skin, color)),
        )
    return result


def publish(root, seats, players, accounts=None):
    data = json.dumps(appearances(seats, players, accounts), ensure_ascii=False)
    target = root / "world/gamenight/profiles.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_text(encoding="utf8") == data:
        return
    temp = target.with_suffix(".tmp")
    temp.write_text(data, encoding="utf8")
    temp.replace(target)
