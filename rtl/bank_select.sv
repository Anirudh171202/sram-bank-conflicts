// Bank-select functions: which bank a word address lives in, and which slot
// inside that bank. Every variant must map distinct addresses to distinct
// (bank, slot) pairs; the testbench's data check catches any aliasing.
// Kept as standalone modules so Yosys can count the gates each one costs.
// Addresses are 9 bits: the padded layout (17 words/row) reaches word 270.
// Banks and slots are 5 bits so the 17-bank variant fits.

// Plain hardware: low address bits pick the bank.
module bank_select_slice (
  input  logic [8:0] addr,
  output logic [4:0] bank,
  output logic [4:0] slot
);
  assign bank = {1'b0, addr[3:0]};
  assign slot = addr[8:4];
endmodule

// Swizzled hardware: XOR the column bits with the row bits.
module bank_select_xor (
  input  logic [8:0] addr,
  output logic [4:0] bank,
  output logic [4:0] slot
);
  assign bank = {1'b0, addr[3:0] ^ addr[7:4]};
  assign slot = addr[8:4];
endmodule

// Block-cyclic: low 2 bits of the row and of the column pick the bank, so
// every aligned 4x4 block spans all 16 banks.
module bank_select_block (
  input  logic [8:0] addr,
  output logic [4:0] bank,
  output logic [4:0] slot
);
  assign bank = {1'b0, addr[5:4], addr[1:0]};
  assign slot = {addr[8:6], addr[3:2]};
endmodule

// Prime bank count: 17 banks, bank = addr mod 17. Addresses sharing
// addr[8:4] differ by less than 17, so they never share a bank and the
// slot can stay a plain bit slice -- no divider needed.
module bank_select_mod17 (
  input  logic [8:0] addr,
  output logic [4:0] bank,
  output logic [4:0] slot
);
  assign bank = 5'(addr % 9'd17);
  assign slot = addr[8:4];
endmodule

// Picks one of the above. MODE: 0 slice, 1 xor, 2 block, 3 mod17.
module bank_select #(
  parameter int MODE = 0
) (
  input  logic [8:0] addr,
  output logic [4:0] bank,
  output logic [4:0] slot
);
  generate
    case (MODE)
      0: bank_select_slice u (.addr, .bank, .slot);
      1: bank_select_xor   u (.addr, .bank, .slot);
      2: bank_select_block u (.addr, .bank, .slot);
      3: bank_select_mod17 u (.addr, .bank, .slot);
    endcase
  endgenerate
endmodule
