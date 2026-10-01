"""Search every XOR bank function of the form  bank = column XOR (R * row).

R is a 4x4 bit matrix: bank bit i XORs in the row bits where R[i] has a 1.
Each 1 costs one XOR gate. There are 2^16 = 65,536 choices of R. For each one,
score the total cycles of the three GEMV dataflows in gen.py (best possible is
3 x 16 = 48) and keep the fastest wiring at each gate count: the Pareto frontier.

Standard swizzle (bank_select_xor):  R = identity            -> row bit i into bank bit i
Rotated swizzle (bank_select_rotxor): R = rows rotated by 2  -> row bit i into bank bit i+2

Writes:
  results/xor_search.csv   gates, best_cycles, wirings, perfect_wirings
  results/xor_pareto.png
"""

import csv
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt

from gen import DATAFLOWS, N

RESULTS = Path(__file__).parent / "results"
BEST_POSSIBLE = len(DATAFLOWS) * N

STANDARD = (0b0001, 0b0010, 0b0100, 0b1000)
ROTATED  = (0b0100, 0b1000, 0b0001, 0b0010)

SERIES, ACCENT = "#2a78d6", "#eb6834"
SURFACE, TEXT, TEXT_2, GRID, DOTS = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#b9b8b2"


def bank(R, r, c):
    mix = 0
    for i, mask in enumerate(R):
        mix |= (bin(mask & r).count("1") & 1) << i
    return c ^ mix


def gates(R):
    return sum(bin(mask).count("1") for mask in R)


def total_cycles(R):
    return sum(max(Counter(bank(R, r, c) for r, c in read).values())
               for steps in DATAFLOWS.values() for read in steps)


def search():
    points = defaultdict(set)     # gates -> set of total cycles reached
    count = Counter()             # gates -> number of wirings
    perfect = Counter()           # gates -> number of wirings hitting BEST_POSSIBLE
    for k in range(1 << 16):
        R = tuple((k >> (4 * i)) & 0xF for i in range(4))
        g, t = gates(R), total_cycles(R)
        points[g].add(t)
        count[g] += 1
        perfect[g] += t == BEST_POSSIBLE
    return points, count, perfect


def plot(points, frontier, count, perfect):
    fig, ax = plt.subplots(figsize=(8, 5), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    xs = [g for g in points for _ in points[g]]
    ys = [t for g in points for t in points[g]]
    ax.scatter(xs, ys, s=14, color=DOTS, zorder=2, label="other wirings")

    fx = sorted(frontier)
    ax.plot(fx, [frontier[g] for g in fx], color=SERIES, lw=2, zorder=3)
    ax.scatter(fx, [frontier[g] for g in fx], s=36, color=SERIES, zorder=4,
               edgecolor=SURFACE, linewidth=1.5, label="fastest at each gate count")

    ax.axhline(BEST_POSSIBLE, color=TEXT_2, lw=1, ls=(0, (4, 3)), zorder=1)
    ax.text(16, BEST_POSSIBLE - 6, "conflict-free on all three dataflows (48)",
            ha="right", va="top", fontsize=8, color=TEXT_2)

    std = (gates(STANDARD), total_cycles(STANDARD))
    rot = (gates(ROTATED), total_cycles(ROTATED))
    ax.scatter(*std, s=60, color=ACCENT, zorder=5, edgecolor=SURFACE, linewidth=1.5)
    box = dict(boxstyle="round,pad=0.25", facecolor=SURFACE, edgecolor="none")
    ax.annotate(f"standard XOR swizzle\n{std[0]} gates, {std[1]} cycles", std,
                xytext=(5.2, 245), textcoords="data", ha="left", fontsize=8,
                color=TEXT, bbox=box, zorder=6,
                arrowprops=dict(arrowstyle="-", color=TEXT_2, lw=0.8))
    ax.annotate(f"rotated XOR swizzle\n{rot[0]} gates, {rot[1]} cycles"
                f"  (only {perfect[rot[0]]} of {count[rot[0]]:,}\n{rot[0]}-gate wirings are this fast)",
                rot, xytext=(12, -34), textcoords="offset points", fontsize=8, color=TEXT,
                bbox=box, zorder=6, arrowprops=dict(arrowstyle="-", color=TEXT_2, lw=0.8))
    ax.annotate("plain slice (no XOR)\n0 gates, 336 cycles", (0, frontier[0]),
                xytext=(14, -6), textcoords="offset points", fontsize=8, color=TEXT)

    ax.set_xlim(-0.6, 16.6)
    ax.set_ylim(0, 380)
    ax.set_xticks(range(0, 17, 2))
    ax.set_xlabel("XOR gates per lane", color=TEXT_2, fontsize=9)
    ax.set_ylabel("Total GEMV cycles (3 dataflows)", color=TEXT_2, fontsize=9)
    ax.tick_params(colors=TEXT_2, labelsize=8, length=0)
    ax.grid(color=GRID, lw=0.8, zorder=0)
    for side in ax.spines.values():
        side.set_visible(False)

    ax.set_title("Four gates is enough, if they're the right four",
                 loc="left", color=TEXT, fontsize=12, fontweight="bold", pad=44)
    ax.text(0, 1.075, "All 65,536 XOR bank functions  bank = column ⊕ (R · row),  on one 16×16 GEMV tile",
            transform=ax.transAxes, color=TEXT_2, fontsize=9)
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.0), ncol=2, frameon=False,
              fontsize=8, labelcolor=TEXT, handlelength=1.2, columnspacing=1.6)

    fig.tight_layout()
    fig.savefig(RESULTS / "xor_pareto.png", facecolor=SURFACE)


def main():
    points, count, perfect = search()
    frontier = {g: min(ts) for g, ts in points.items()}

    with open(RESULTS / "xor_search.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["gates", "best_cycles", "wirings", "perfect_wirings"])
        for g in sorted(points):
            w.writerow([g, frontier[g], count[g], perfect[g]])

    print(f"{'gates':>5} {'best cycles':>12} {'wirings':>8} {'perfect':>8}")
    for g in sorted(points):
        print(f"{g:>5} {frontier[g]:>12} {count[g]:>8} {perfect[g]:>8}")
    print(f"\nstandard XOR: {gates(STANDARD)} gates, {total_cycles(STANDARD)} cycles")
    print(f"rotated XOR:  {gates(ROTATED)} gates, {total_cycles(ROTATED)} cycles")
    plot(points, frontier, count, perfect)


if __name__ == "__main__":
    main()
