"""Compare the GEMV runs against a summed-data-movement estimate.

The estimate is the model Timeloop and Interstellar use for a buffer: words
read / words the buffer delivers per cycle. It sees only how many words move,
so it gives every layout and dataflow the same answer. The RTL cycles come from
results/gemv.csv (run.py), and the busiest-bank estimate is gen.py's reference.

Writes:
  results/comparison.csv
  results/gemv_bandwidth.png
"""

import csv
from pathlib import Path

import matplotlib.pyplot as plt

from gen import DATAFLOWS, LAYOUTS, N, WORD_BYTES

RESULTS = Path(__file__).parent / "results"
LANES = N                      # the buffer delivers at most one word per lane per cycle
PEAK_BYTES_PER_CYCLE = LANES * WORD_BYTES

# One color per dataflow, from a colorblind-safe categorical palette.
COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]
SURFACE, TEXT, TEXT_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"


def load():
    with open(RESULTS / "gemv.csv") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        words = int(r["bytes"]) // WORD_BYTES
        rtl = int(r["rtl_cycles"])
        summed = words // LANES
        out.append({
            "layout": r["layout"],
            "dataflow": r["dataflow"],
            "bytes": int(r["bytes"]),
            "summed_estimate_cycles": summed,
            "busiest_bank_estimate_cycles": int(r["ref_cycles"]),
            "rtl_cycles": rtl,
            "bytes_per_cycle": round(int(r["bytes"]) / rtl, 2),
            "pct_of_estimate": round(100 * summed / rtl, 1),
        })
    return out


def plot(rows):
    layouts, dataflows = list(LAYOUTS), list(DATAFLOWS)
    pct = {(r["layout"], r["dataflow"]): r["pct_of_estimate"] for r in rows}

    fig, ax = plt.subplots(figsize=(8, 5.2), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    bar_h, gap = 0.24, 0.03
    for j, (dataflow, color) in enumerate(zip(dataflows, COLORS)):
        ys = [i + (j - 1) * (bar_h + gap) for i in range(len(layouts))]
        vals = [pct[(l, dataflow)] for l in layouts]
        ax.barh(ys, vals, height=bar_h, color=color, label=dataflow, zorder=3)
        for y, v in zip(ys, vals):
            ax.text(v + 1.2, y, f"{v:.0f}%", va="center", ha="left", fontsize=7.5, color=TEXT_2)

    ax.axvline(100, color=TEXT, lw=1.2, ls=(0, (4, 3)), zorder=4)
    ax.text(99, len(layouts) - 0.38, "summed-data-movement estimate", ha="right", va="center",
            fontsize=8, color=TEXT)

    ax.set_yticks(range(len(layouts)), layouts, color=TEXT, fontsize=9)
    ax.set_ylim(len(layouts) - 0.2, -0.5)
    ax.set_xlim(0, 112)
    ax.set_xticks(range(0, 101, 25), [f"{t}%" for t in range(0, 101, 25)], color=TEXT_2, fontsize=8)
    ax.set_xlabel("Achieved throughput, % of estimate", color=TEXT_2, fontsize=9)
    ax.grid(axis="x", color=GRID, lw=0.8, zorder=0)
    ax.tick_params(length=0)
    for side in ax.spines.values():
        side.set_visible(False)

    ax.set_title("Same 1 KiB of weights, very different throughput",
                 loc="left", color=TEXT, fontsize=12, fontweight="bold", pad=44)
    ax.text(0, 1.075, "GEMV on one 16×16 tile in a 16-bank SRAM, measured in RTL simulation",
            transform=ax.transAxes, color=TEXT_2, fontsize=9)
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.0), ncol=3, frameon=False,
              fontsize=8, labelcolor=TEXT, handlelength=1.2, columnspacing=1.6)

    fig.tight_layout()
    fig.savefig(RESULTS / "gemv_bandwidth.png", facecolor=SURFACE)


def main():
    rows = load()
    with open(RESULTS / "comparison.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)

    print(f"Peak: {PEAK_BYTES_PER_CYCLE} B/cycle. Summed-data-movement estimate: "
          f"{rows[0]['summed_estimate_cycles']} cycles for every row.\n")
    print(f"{'layout':13} {'dataflow':18} {'RTL':>5} {'busiest-bank':>13} {'B/cycle':>8} {'% of est.':>10}")
    for r in rows:
        print(f"{r['layout']:13} {r['dataflow']:18} {r['rtl_cycles']:>5} "
              f"{r['busiest_bank_estimate_cycles']:>13} {r['bytes_per_cycle']:>8} {r['pct_of_estimate']:>9}%")
    plot(rows)


if __name__ == "__main__":
    main()
