"""Create the multi-size Windows icon used by the standalone executable."""
import struct
import zlib


SIZES = (16, 24, 32, 48, 64, 128, 256)


def pixel(x, y, size):
    # Rounded violet tile with Aster's two-star mark.
    radius = size * 0.27
    dx = max(radius - x, 0, x - (size - radius - 1))
    dy = max(radius - y, 0, y - (size - radius - 1))
    inside = dx * dx + dy * dy <= radius * radius
    if not inside:
        return 0, 0, 0, 0
    t = (x + y) / max(1, 2 * (size - 1))
    r, g, b = int(142 - 54 * t), int(133 - 55 * t), int(255 - 25 * t)
    u, v = x / size, y / size
    big = abs(u - .43) ** (2 / 3) + abs(v - .58) ** (2 / 3) <= .27 ** (2 / 3)
    small = abs(u - .745) ** (2 / 3) + abs(v - .27) ** (2 / 3) <= .115 ** (2 / 3)
    if big or small:
        r, g, b = 255, 255, 255
    return r, g, b, 255


def png(size):
    raw = bytearray()
    for y in range(size):
        raw.append(0)
        for x in range(size):
            raw.extend(pixel(x, y, size))

    def chunk(name, data):
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data) & 0xffffffff)

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")


entries = [png(size) for size in SIZES]
offset = 6 + 16 * len(entries)
directory = bytearray(struct.pack("<HHH", 0, 1, len(entries)))
for size, data in zip(SIZES, entries):
    directory.extend(struct.pack("<BBBBHHII", size if size < 256 else 0, size if size < 256 else 0, 0, 0, 1, 32, len(data), offset))
    offset += len(data)

with open("aster.ico", "wb") as out:
    out.write(directory)
    for data in entries:
        out.write(data)
