"""Simulate every layout x pattern in the Verilog model and check it against gen.py.

Writes:
  results/results.csv        layout, pattern, bytes, rtl_cycles, ref_cycles
  results/trace_<layout>.csv every served read, for the replay animation
"""

import csv
import re
import subprocess
import sys
from pathlib import Path

from gen import LAYOUTS, MODE, N, PATTERNS, WORD_BYTES, addresses, reference_cycles

ROOT = Path(__file__).parent
BUILD = ROOT / "build"
RESULTS = ROOT / "results"
RTL = [ROOT / "rtl" / f for f in ("bank_select.sv", "banked_sram.sv", "tb.sv")]
RESULT_RE = re.compile(r"RESULT req=(\d+) cycles=(\d+) errors=(\d+)")


def compile_sim(select):
    out = BUILD / f"sim_{select}.vvp"
    subprocess.run(
        ["iverilog", "-g2012", f"-Ptb.MODE={MODE[select]}", "-o", str(out), *map(str, RTL)],
        check=True,
    )
    return out


def simulate(sim, layout):
    reqfile = BUILD / f"{layout}.hex"
    with open(reqfile, "w") as f:
        for pattern in PATTERNS:
            f.writelines(f"{a:03x}\n" for a in addresses(layout, pattern))
    trace = RESULTS / f"trace_{layout}.csv"
    proc = subprocess.run(
        ["vvp", "-n", str(sim), f"+reqs={reqfile}", f"+nreq={len(PATTERNS)}", f"+trace={trace}"],
        check=True, capture_output=True, text=True,
    )
    return [(int(c), int(e)) for _, c, e in RESULT_RE.findall(proc.stdout)]


def main():
    BUILD.mkdir(exist_ok=True)
    RESULTS.mkdir(exist_ok=True)
    sims = {s: compile_sim(s) for s in {sel for _, sel in LAYOUTS.values()}}

    rows, failures = [], 0
    for layout, (_, select) in LAYOUTS.items():
        results = simulate(sims[select], layout)
        assert len(results) == len(PATTERNS), f"{layout}: got {len(results)} results"
        for pattern, (cycles, errors) in zip(PATTERNS, results):
            ref = reference_cycles(layout, pattern)
            ok = cycles == ref and errors == 0
            failures += not ok
            rows.append({
                "layout": layout, "pattern": pattern, "bytes": N * WORD_BYTES,
                "rtl_cycles": cycles, "ref_cycles": ref,
            })
            flag = "ok" if ok else f"MISMATCH (ref {ref}, data errors {errors})"
            print(f"{layout:10} {pattern:10} {cycles:3} cycles  {flag}")

    with open(RESULTS / "results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)

    print(f"\n{len(rows) - failures}/{len(rows)} cells match the reference model")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
