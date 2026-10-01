#!/usr/bin/env bash
# Gate counts (Yosys generic gate library) for the logic that decides which
# bank each lane reads. The storage itself is left out: real SRAM banks are
# hard macros, and synthesizing them as flops would swamp every other number.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p results

out=results/synth.csv
echo "module,cells" > "$out"

for top in bank_select_slice bank_select_xor bank_select_block bank_select_mod17 bank_select_rotxor bank_arbiter; do
  n=$(yosys -q -p "read_verilog -sv rtl/bank_select.sv rtl/banked_sram.sv; synth -top $top; tee -o /dev/stdout stat" \
      | awk '/ cells$/ {print $1; exit}')
  n=${n:-0}  # yosys omits the cells line for pure-wire modules
  echo "$top,$n" >> "$out"
  printf "%-20s %6s cells\n" "$top" "$n"
done

# The prime layout also needs a 17th bank, which grows the arbiter.
n=$(yosys -q -p "read_verilog -sv rtl/bank_select.sv rtl/banked_sram.sv; chparam -set BANKS 17 bank_arbiter; synth -top bank_arbiter; tee -o /dev/stdout stat" \
    | awk '/ cells$/ {print $1; exit}')
echo "bank_arbiter_17,$n" >> "$out"
printf "%-20s %6s cells\n" "bank_arbiter_17" "$n"
