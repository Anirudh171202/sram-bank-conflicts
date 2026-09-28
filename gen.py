"""Layouts, access patterns and a Python reference model for the banked SRAM.

A 16x16 tile is read by 16 lanes at once. Each layout places cell (r, c) at a
word address and pairs it with a hardware bank-select. A request takes as many
cycles as its most-loaded bank has lanes. The bank-selects mirror
rtl/bank_select.sv, and their order there gives each one's MODE number.
"""

from collections import Counter

N = 16          # tile is N x N, also the number of lanes
WORD_BYTES = 4

# name -> (address of cell (r, c), hardware bank-select)
LAYOUTS = {
    "row-major": (lambda r, c: N * r + c,       "slice"),
    "padded":    (lambda r, c: (N + 1) * r + c, "slice"),
    "swizzled":  (lambda r, c: N * r + c,       "xor"),
    "block-cyclic": (lambda r, c: N * r + c,    "block"),
    "prime-17":  (lambda r, c: N * r + c,       "mod17"),
}

BANK_SELECT = {
    "slice": lambda a: a & 0xF,
    "xor":   lambda a: (a & 0xF) ^ ((a >> 4) & 0xF),
    "block": lambda a: (((a >> 4) & 0x3) << 2) | (a & 0x3),
    "mod17": lambda a: a % 17,
}
MODE = {name: i for i, name in enumerate(BANK_SELECT)}

# name -> list of (r, c), one cell per lane
PATTERNS = {
    "row":       [(0, i) for i in range(N)],
    "column":    [(i, 0) for i in range(N)],
    "diagonal":  [(i, i) for i in range(N)],
    "anti-diag": [(i, N - 1 - i) for i in range(N)],
    "block":     [(i // 4, i % 4) for i in range(N)],
}


def addresses(layout, pattern):
    place, _ = LAYOUTS[layout]
    return [place(r, c) for r, c in PATTERNS[pattern]]


def banks(layout, pattern):
    _, select = LAYOUTS[layout]
    return [BANK_SELECT[select](a) for a in addresses(layout, pattern)]


def reference_cycles(layout, pattern):
    return max(Counter(banks(layout, pattern)).values())


def bank_map(layout):
    """N x N grid of the bank each cell lives in -- the 'picture' of a layout."""
    place, select = LAYOUTS[layout]
    return [[BANK_SELECT[select](place(r, c)) for c in range(N)] for r in range(N)]


if __name__ == "__main__":
    print(f"{'':10}" + "".join(f"{p:>11}" for p in PATTERNS))
    for layout in LAYOUTS:
        print(f"{layout:10}" + "".join(f"{reference_cycles(layout, p):>11}" for p in PATTERNS))
