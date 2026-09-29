"""Simulate every layout x pattern, and every layout x GEMV dataflow, in the
Verilog model and check each against gen.py.

Writes:
  results/results.csv        layout, pattern, bytes, rtl_cycles, ref_cycles
  results/gemv.csv           layout, dataflow, bytes, rtl_cycles, ref_cycles
  results/trace_<layout>.csv every served read of the patterns, for the replay
"""

import csv
import re
import subprocess
import sys
from pathlib import Path

from gen import DATAFLOWS, LAYOUTS, MODE, N, PATTERNS, WORD_BYTES, addresses, reference_cycles

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


def simulate(sim, layout, reads, name, trace=False):
    """Run a list of 16-lane reads; return (cycles, data errors) per read."""
    reqfile = BUILD / f"{name}.hex"
    with open(reqfile, "w") as f:
        for cells in reads:
            f.writelines(f"{a:03x}\n" for a in addresses(layout, cells))
    args = ["vvp", "-n", str(sim), f"+reqs={reqfile}", f"+nreq={len(reads)}"]
    if trace:
        args.append(f"+trace={RESULTS / f'trace_{name}.csv'}")
    proc = subprocess.run(args, check=True, capture_output=True, text=True)
    results = [(int(c), int(e)) for _, c, e in RESULT_RE.findall(proc.stdout)]
    assert len(results) == len(reads), f"{name}: got {len(results)} of {len(reads)} results"
    return results


def write_csv(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)


def main():
    BUILD.mkdir(exist_ok=True)
    RESULTS.mkdir(exist_ok=True)
    sims = {s: compile_sim(s) for s in {sel for _, sel in LAYOUTS.values()}}

    rows, failures = [], 0
    for layout, (_, select) in LAYOUTS.items():
        results = simulate(sims[select], layout, list(PATTERNS.values()), layout, trace=True)
        for (pattern, cells), (cycles, errors) in zip(PATTERNS.items(), results):
            ref = reference_cycles(layout, cells)
            ok = cycles == ref and errors == 0
            failures += not ok
            rows.append({
                "layout": layout, "pattern": pattern, "bytes": N * WORD_BYTES,
                "rtl_cycles": cycles, "ref_cycles": ref,
            })
            flag = "ok" if ok else f"MISMATCH (ref {ref}, data errors {errors})"
            print(f"{layout:13} {pattern:22} {cycles:4} cycles  {flag}")
    write_csv(RESULTS / "results.csv", rows)

    gemv = []
    for layout, (_, select) in LAYOUTS.items():
        for dataflow, steps in DATAFLOWS.items():
            results = simulate(sims[select], layout, steps, f"gemv_{layout}_{dataflow}")
            cycles = sum(c for c, _ in results)
            errors = sum(e for _, e in results)
            ref = sum(reference_cycles(layout, cells) for cells in steps)
            ok = cycles == ref and errors == 0
            failures += not ok
            gemv.append({
                "layout": layout, "dataflow": dataflow,
                "bytes": len(steps) * N * WORD_BYTES, "rtl_cycles": cycles, "ref_cycles": ref,
            })
            flag = "ok" if ok else f"MISMATCH (ref {ref}, data errors {errors})"
            print(f"{layout:13} gemv {dataflow:17} {cycles:4} cycles  {flag}")
    write_csv(RESULTS / "gemv.csv", gemv)

    total = len(rows) + len(gemv)
    print(f"\n{total - failures}/{total} runs match the reference model")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
