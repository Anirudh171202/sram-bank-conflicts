// Banked scratchpad SRAM read by 16 lanes at once.
//
// Each bank serves one read per cycle. When several lanes target the same
// bank, the lowest-numbered pending lane wins and the rest wait, so a request
// takes as many cycles as its most-loaded bank has lanes.
//
// Word address -> (bank, slot) comes from bank_select, chosen by MODE
// (0 slice, 1 xor, 2 block, 3 mod17). MODE 3 uses 17 banks, the rest 16.

module banked_sram #(
  parameter int LANES = 16,
  parameter int AW    = 9,
  parameter int DW    = 32,
  parameter int MODE  = 0
) (
  input  logic                  clk,
  input  logic                  rst,

  // Preload port (one word per cycle).
  input  logic                  we,
  input  logic [AW-1:0]         waddr,
  input  logic [DW-1:0]         wdata,

  // Read request: all lanes at once.
  input  logic                  start,
  input  logic [LANES*AW-1:0]   addrs,
  output logic                  busy,
  output logic                  done,        // pulses on the cycle the last lane is served
  output logic [LANES*DW-1:0]   rdata,
  output logic [15:0]           cycles,      // cycles the last request took

  // Observability for the replay animation.
  output logic [LANES-1:0]      grant,       // lanes served this cycle
  output logic [LANES*5-1:0]    lane_bank    // bank each lane targets
);
  localparam int BANKS = (MODE == 3) ? 17 : 16;
  localparam int DEPTH = 32;

  logic [DW-1:0]       mem [BANKS][DEPTH];
  logic [LANES*AW-1:0] addr_q;
  logic [LANES*5-1:0]  lane_slot;
  logic [LANES-1:0]    pending;
  logic [4:0]          wbank, wslot;

  assign busy = |pending;

  // One bank-select per lane, plus one for the preload port.
  genvar g;
  generate
    for (g = 0; g < LANES; g++) begin : g_sel
      bank_select #(.MODE(MODE)) u (
        .addr(addr_q[g*AW +: AW]), .bank(lane_bank[g*5 +: 5]), .slot(lane_slot[g*5 +: 5])
      );
    end
  endgenerate
  bank_select #(.MODE(MODE)) u_wsel (.addr(waddr), .bank(wbank), .slot(wslot));

  bank_arbiter #(.LANES(LANES), .BANKS(BANKS)) u_arb (
    .pending, .lane_bank, .grant
  );

  always_ff @(posedge clk) begin
    if (rst) begin
      pending <= '0;
      cycles  <= '0;
      done    <= 1'b0;
    end else begin
      done <= 1'b0;

      if (start && !busy) begin
        addr_q  <= addrs;
        pending <= '1;
        cycles  <= '0;
      end else if (busy) begin
        for (int l = 0; l < LANES; l++)
          if (grant[l])
            rdata[l*DW +: DW] <= mem[lane_bank[l*5 +: 5]][lane_slot[l*5 +: 5]];
        pending <= pending & ~grant;
        cycles  <= cycles + 1'b1;
        if ((pending & ~grant) == '0) done <= 1'b1;
      end

      if (we) mem[wbank][wslot] <= wdata;
    end
  end
endmodule

// Per-bank arbiter: each bank grants its lowest-numbered pending lane.
// Separate module so Yosys can count its gates on their own.
module bank_arbiter #(
  parameter int LANES = 16,
  parameter int BANKS = 16
) (
  input  logic [LANES-1:0]   pending,
  input  logic [LANES*5-1:0] lane_bank,
  output logic [LANES-1:0]   grant
);
  always_comb begin
    logic taken;
    grant = '0;
    for (int b = 0; b < BANKS; b++) begin
      taken = 1'b0;
      for (int l = 0; l < LANES; l++) begin
        if (!taken && pending[l] && lane_bank[l*5 +: 5] == b) begin
          grant[l] = 1'b1;
          taken    = 1'b1;
        end
      end
    end
  end
endmodule
