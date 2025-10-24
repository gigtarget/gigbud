from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

# Galois field setup for GF(256)
POLY = 0x11D
EXP_TABLE = [0] * 512
LOG_TABLE = [0] * 256

def _init_tables() -> None:
    x = 1
    for i in range(255):
        EXP_TABLE[i] = x
        LOG_TABLE[x] = i
        x <<= 1
        if x & 0x100:
            x ^= POLY
    for i in range(255, 512):
        EXP_TABLE[i] = EXP_TABLE[i - 255]

_init_tables()

def gf_mul(x: int, y: int) -> int:
    if x == 0 or y == 0:
        return 0
    return EXP_TABLE[LOG_TABLE[x] + LOG_TABLE[y]]


def rs_generator_poly(degree: int) -> List[int]:
    result = [1]
    for i in range(degree):
        result = poly_mul(result, [1, EXP_TABLE[i]])
    return result


def poly_mul(p: List[int], q: List[int]) -> List[int]:
    res = [0] * (len(p) + len(q) - 1)
    for i, a in enumerate(p):
        for j, b in enumerate(q):
            res[i + j] ^= gf_mul(a, b)
    return res


def rs_compute_remainder(data: List[int], generator: List[int]) -> List[int]:
    result = data[:] + [0] * (len(generator) - 1)
    for i in range(len(data)):
        coef = result[i]
        if coef == 0:
            continue
        for j in range(len(generator)):
            result[i + j] ^= gf_mul(generator[j], coef)
    return result[-(len(generator) - 1):]


@dataclass
class VersionInfo:
    version: int
    size: int
    total_codewords: int
    data_codewords: int
    ecc_codewords: int
    ecc_blocks: int


VERSION_TABLE = [
    VersionInfo(version=1, size=21, total_codewords=26, data_codewords=19, ecc_codewords=7, ecc_blocks=1),
    VersionInfo(version=2, size=25, total_codewords=44, data_codewords=34, ecc_codewords=10, ecc_blocks=1),
    VersionInfo(version=3, size=29, total_codewords=70, data_codewords=55, ecc_codewords=15, ecc_blocks=1),
    VersionInfo(version=4, size=33, total_codewords=100, data_codewords=80, ecc_codewords=20, ecc_blocks=1),
]


ECC_LEVEL_FORMAT = {
    'L': 0b01,
    'M': 0b00,
    'Q': 0b11,
    'H': 0b10,
}


class QRMatrix:
    def __init__(self, size: int) -> None:
        self.size = size
        self.modules: List[List[Optional[bool]]] = [[None for _ in range(size)] for _ in range(size)]
        self.is_function: List[List[bool]] = [[False for _ in range(size)] for _ in range(size)]

    def set_function(self, x: int, y: int, value: bool) -> None:
        self.modules[y][x] = value
        self.is_function[y][x] = True

    def set_data(self, x: int, y: int, value: bool) -> None:
        if self.is_function[y][x]:
            raise ValueError("Attempting to overwrite function module")
        self.modules[y][x] = value

    def get(self, x: int, y: int) -> Optional[bool]:
        return self.modules[y][x]


FINDER_PATTERN = [
    [True, True, True, True, True, True, True],
    [True, False, False, False, False, False, True],
    [True, False, True, True, True, False, True],
    [True, False, True, True, True, False, True],
    [True, False, True, True, True, False, True],
    [True, False, False, False, False, False, True],
    [True, True, True, True, True, True, True],
]

ALIGNMENT_PATTERN = [
    [True, True, True, True, True],
    [True, False, False, False, True],
    [True, False, True, False, True],
    [True, False, False, False, True],
    [True, True, True, True, True],
]

ALIGNMENT_POSITIONS = {
    1: [],
    2: [6, 18],
    3: [6, 22],
    4: [6, 26],
}


def place_finder(matrix: QRMatrix, x: int, y: int) -> None:
    for dy in range(7):
        for dx in range(7):
            matrix.set_function(x + dx, y + dy, FINDER_PATTERN[dy][dx])
    # Separator
    for i in range(-1, 8):
        for dx, dy in ((-1, i), (7, i), (i, -1), (i, 7)):
            xx, yy = x + dx, y + dy
            if 0 <= xx < matrix.size and 0 <= yy < matrix.size and matrix.get(xx, yy) is None:
                matrix.set_function(xx, yy, False)


def place_alignment(matrix: QRMatrix, version: int) -> None:
    positions = ALIGNMENT_POSITIONS.get(version, [])
    if not positions:
        return
    for y in positions:
        for x in positions:
            if (x <= 7 and y <= 7) or (x >= matrix.size - 8 and y <= 7) or (x <= 7 and y >= matrix.size - 8):
                continue
            for dy in range(5):
                for dx in range(5):
                    matrix.set_function(x - 2 + dx, y - 2 + dy, ALIGNMENT_PATTERN[dy][dx])


def place_timing(matrix: QRMatrix) -> None:
    for i in range(8, matrix.size - 8):
        bit = (i % 2) == 0
        if matrix.get(i, 6) is None:
            matrix.set_function(i, 6, bit)
        if matrix.get(6, i) is None:
            matrix.set_function(6, i, bit)


def place_dark_module(matrix: QRMatrix) -> None:
    matrix.set_function(8, matrix.size - 8, True)


def reserve_format_info(matrix: QRMatrix) -> None:
    size = matrix.size
    for i in range(9):
        if i != 6:
            matrix.set_function(8, i, False)
            matrix.set_function(i, 8, False)
    for i in range(8):
        if i != 6:
            matrix.set_function(size - 1 - i, 8, False)
            y = size - 1 - i
            if y != size - 8:
                matrix.set_function(8, y, False)


def format_info_bits(ecc_level: str, mask: int) -> int:
    format_value = (ECC_LEVEL_FORMAT[ecc_level] << 3) | mask
    # Apply BCH(15,5)
    g = 0b10100110111
    value = format_value << 10
    for i in reversed(range(10, -1, -1)):
        if (value >> (i + 10)) & 1:
            value ^= g << i
    format_bits = ((format_value << 10) | value) ^ 0b101010000010010
    return format_bits


def apply_format_info(matrix: QRMatrix, ecc_level: str, mask: int) -> None:
    bits = format_info_bits(ecc_level, mask)
    size = matrix.size
    for i in range(0, 6):
        matrix.set_function(8, i, ((bits >> i) & 1) == 1)
    matrix.set_function(8, 7, ((bits >> 6) & 1) == 1)
    matrix.set_function(8, 8, ((bits >> 7) & 1) == 1)
    matrix.set_function(7, 8, ((bits >> 8) & 1) == 1)
    for i in range(9, 15):
        matrix.set_function(14 - i, 8, ((bits >> i) & 1) == 1)

    for i in range(0, 8):
        matrix.set_function(size - 1 - i, 8, ((bits >> i) & 1) == 1)
    for i in range(0, 7):
        matrix.set_function(8, size - 7 + i, ((bits >> (i + 8)) & 1) == 1)


def apply_mask(x: int, y: int, mask: int) -> bool:
    if mask == 0:
        return (x + y) % 2 == 0
    elif mask == 1:
        return y % 2 == 0
    elif mask == 2:
        return x % 3 == 0
    elif mask == 3:
        return (x + y) % 3 == 0
    elif mask == 4:
        return ((y // 2) + (x // 3)) % 2 == 0
    elif mask == 5:
        return ((x * y) % 2) + ((x * y) % 3) == 0
    elif mask == 6:
        return (((x * y) % 2) + ((x * y) % 3)) % 2 == 0
    elif mask == 7:
        return (((x + y) % 2) + ((x * y) % 3)) % 2 == 0
    else:
        raise ValueError("Invalid mask")


def penalty_score(matrix: QRMatrix) -> int:
    size = matrix.size
    # Convert to bool matrix for convenience
    grid = [[bool(matrix.modules[y][x]) for x in range(size)] for y in range(size)]
    penalty = 0

    # Adjacent modules in row/col with same color
    for y in range(size):
        run_color = grid[y][0]
        run_length = 1
        for x in range(1, size):
            if grid[y][x] == run_color:
                run_length += 1
            else:
                if run_length >= 5:
                    penalty += 3 + (run_length - 5)
                run_color = grid[y][x]
                run_length = 1
        if run_length >= 5:
            penalty += 3 + (run_length - 5)

    for x in range(size):
        run_color = grid[0][x]
        run_length = 1
        for y in range(1, size):
            if grid[y][x] == run_color:
                run_length += 1
            else:
                if run_length >= 5:
                    penalty += 3 + (run_length - 5)
                run_color = grid[y][x]
                run_length = 1
        if run_length >= 5:
            penalty += 3 + (run_length - 5)

    # 2x2 blocks
    for y in range(size - 1):
        for x in range(size - 1):
            if grid[y][x] == grid[y][x + 1] == grid[y + 1][x] == grid[y + 1][x + 1]:
                penalty += 3

    # Finder-like patterns in rows and columns
    pattern1 = [True, False, True, True, True, False, True, False, False, False, False]
    pattern2 = [False, False, False, False, True, False, True, True, True, False, True]
    for row in grid:
        for i in range(size - 10):
            if row[i:i+11] == pattern1 or row[i:i+11] == pattern2:
                penalty += 40
    for x in range(size):
        column = [grid[y][x] for y in range(size)]
        for i in range(size - 10):
            if column[i:i+11] == pattern1 or column[i:i+11] == pattern2:
                penalty += 40

    # Proportion of dark modules
    dark = sum(row.count(True) for row in grid)
    total = size * size
    k = abs(dark * 20 - total * 10) // total
    penalty += k * 10
    return penalty


def draw_data(matrix: QRMatrix, codewords: List[int], mask: int) -> None:
    size = matrix.size
    bit_index = 0
    total_bits = len(codewords) * 8

    def get_bit(idx: int) -> int:
        return (codewords[idx >> 3] >> (7 - (idx & 7))) & 1

    x = size - 1
    y = size - 1
    direction = -1

    while x > 0:
        if x == 6:
            x -= 1
        while 0 <= y < size:
            for dx in range(2):
                xx = x - dx
                if matrix.get(xx, y) is None:
                    bit = False
                    if bit_index < total_bits:
                        bit = bool(get_bit(bit_index))
                        bit_index += 1
                    if apply_mask(xx, y, mask):
                        bit = not bit
                    matrix.set_data(xx, y, bit)
            y += direction
        y += -direction
        direction = -direction
        x -= 2

    if bit_index != total_bits:
        raise ValueError("Did not place the expected number of bits")


def encode_bytes(data: bytes, version: VersionInfo) -> List[int]:
    mode_bits = 0b0100
    buffer: List[int] = []
    bits: List[int] = []

    def append_bits(value: int, length: int) -> None:
        for i in reversed(range(length)):
            bits.append((value >> i) & 1)

    append_bits(mode_bits, 4)
    append_bits(len(data), 8 if version.version <= 9 else 16)
    for b in data:
        append_bits(b, 8)

    capacity = version.data_codewords * 8
    if len(bits) > capacity:
        raise ValueError("Data too long for selected version")

    terminator = min(4, capacity - len(bits))
    append_bits(0, terminator)
    while len(bits) % 8 != 0:
        bits.append(0)

    pad_bytes = [0xEC, 0x11]
    idx = 0
    while len(bits) < capacity:
        bits.extend([(pad_bytes[idx] >> i) & 1 for i in reversed(range(8))])
        idx ^= 1

    codewords = []
    for i in range(0, len(bits), 8):
        byte = 0
        for bit in bits[i:i+8]:
            byte = (byte << 1) | bit
        codewords.append(byte)
    return codewords


def build_matrix(codewords: List[int], version: VersionInfo, ecc_level: str) -> QRMatrix:
    matrix = QRMatrix(version.size)
    place_finder(matrix, 0, 0)
    place_finder(matrix, version.size - 7, 0)
    place_finder(matrix, 0, version.size - 7)
    place_alignment(matrix, version.version)
    place_timing(matrix)
    place_dark_module(matrix)
    reserve_format_info(matrix)

    best_mask = 0
    best_score = None
    best_modules = None

    for mask in range(8):
        test_matrix = QRMatrix(version.size)
        test_matrix.modules = [row[:] for row in matrix.modules]
        test_matrix.is_function = [row[:] for row in matrix.is_function]

        draw_data(test_matrix, codewords, mask)
        apply_format_info(test_matrix, ecc_level, mask)
        score = penalty_score(test_matrix)
        if best_score is None or score < best_score:
            best_score = score
            best_mask = mask
            best_modules = test_matrix.modules

    final_matrix = QRMatrix(version.size)
    final_matrix.modules = [row[:] for row in matrix.modules]
    final_matrix.is_function = [row[:] for row in matrix.is_function]
    draw_data(final_matrix, codewords, best_mask)
    apply_format_info(final_matrix, ecc_level, best_mask)
    return final_matrix


def choose_version(data: bytes) -> VersionInfo:
    for version in VERSION_TABLE:
        try:
            encode_bytes(data, version)
            return version
        except ValueError:
            continue
    raise ValueError("Data too long for supported versions")


def qr_to_svg(matrix: QRMatrix, scale: int = 10, margin: int = 4) -> str:
    size = matrix.size
    dim = (size + margin * 2) * scale
    rects = []
    for y in range(size):
        for x in range(size):
            if matrix.modules[y][x]:
                xx = (x + margin) * scale
                yy = (y + margin) * scale
                rects.append(f'<rect x="{xx}" y="{yy}" width="{scale}" height="{scale}" />')
    rects_str = "\n        ".join(rects)
    return f"""<?xml version='1.0' encoding='UTF-8'?>
<svg xmlns='http://www.w3.org/2000/svg' width='{dim}' height='{dim}' viewBox='0 0 {dim} {dim}' shape-rendering='crispEdges'>
    <rect width='{dim}' height='{dim}' fill='#ffffff'/>
    <g fill='#000000'>
        {rects_str}
    </g>
</svg>
"""


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate a static QR code SVG.")
    parser.add_argument("data", help="The data to encode in the QR code")
    parser.add_argument("output", help="Path to the SVG file to create")
    args = parser.parse_args()

    data = args.data.encode("utf-8")
    version = choose_version(data)
    data_codewords = encode_bytes(data, version)
    generator = rs_generator_poly(version.ecc_codewords)
    remainder = rs_compute_remainder(data_codewords, generator)
    full_codewords = data_codewords + remainder
    matrix = build_matrix(full_codewords, version, 'L')
    svg = qr_to_svg(matrix)
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(svg)


if __name__ == "__main__":
    main()
