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
    "rotated-xor": (lambda r, c: N * r + c,     "rotxor"),
}

BANK_SELECT = {
    "slice": lambda a: a & 0xF,
    "xor":   lambda a: (a & 0xF) ^ ((a >> 4) & 0xF),
    "block": lambda a: (((a >> 4) & 0x3) << 2) | (a & 0x3),
    "mod17": lambda a: a % 17,
    "rotxor": lambda a: (a & 0xF) ^ ((((a >> 4) & 0x3) << 2) | ((a >> 6) & 0x3)),
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

# GEMV y = W x on one 16x16 weight tile. Each dataflow is a sequence of 16
# reads (one per step), each read one cell per lane. All three read every
# weight exactly once, so they move the same 256 words.
DATAFLOWS = {
    # lane i owns output y[i]; step k reads column k
    "output-stationary": [[(i, k) for i in range(N)] for k in range(N)],
    # lanes split the dot product; step i reads row i
    "split-k":           [[(i, j) for j in range(N)] for i in range(N)],
    # lanes form a 4x4 grid; step s reads one aligned 4x4 block
    "2d-tiled":          [[(4 * (s // 4) + l // 4, 4 * (s % 4) + l % 4) for l in range(N)]
                          for s in range(N)],
}


def addresses(layout, cells):
    place, _ = LAYOUTS[layout]
    return [place(r, c) for r, c in cells]


def banks(layout, cells):
    _, select = LAYOUTS[layout]
    return [BANK_SELECT[select](a) for a in addresses(layout, cells)]


def reference_cycles(layout, cells):
    """Cycles for one read: the number of lanes on the busiest bank."""
    return max(Counter(banks(layout, cells)).values())


def bank_map(layout):
    """N x N grid of the bank each cell lives in -- the 'picture' of a layout."""
    place, select = LAYOUTS[layout]
    return [[BANK_SELECT[select](place(r, c)) for c in range(N)] for r in range(N)]


if __name__ == "__main__":
    print(f"{'':13}" + "".join(f"{p:>11}" for p in PATTERNS))
    for layout in LAYOUTS:
        print(f"{layout:13}" + "".join(
            f"{reference_cycles(layout, cells):>11}" for cells in PATTERNS.values()))
    print(f"\nGEMV tile{'':4}" + "".join(f"{d:>19}" for d in DATAFLOWS))
    for layout in LAYOUTS:
        print(f"{layout:13}" + "".join(
            f"{sum(reference_cycles(layout, read) for read in steps):>19}"
            for steps in DATAFLOWS.values()))
