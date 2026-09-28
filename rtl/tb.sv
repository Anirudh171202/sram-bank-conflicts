// Replays a file of 16-lane read requests against banked_sram.
//
// Plusargs:
//   +reqs=<file>   $readmemh file, 16 word addresses per request
//   +nreq=<n>      number of requests in the file
//   +trace=<file>  optional CSV log of every served read: req,cycle,lane,bank
//
// Prints one "RESULT req=<i> cycles=<n> errors=<e>" line per request.
// Memory is preloaded with a tag derived from each address, so a wrong
// bank mapping shows up as a data error, not just a wrong cycle count.

`timescale 1ns/1ps

module tb;
  parameter int MODE = 0;

  localparam int LANES  = 16;
  localparam int AW     = 9;
  localparam int DW     = 32;
  localparam int WORDS  = 1 << AW;
  localparam int MAXREQ = 64;

  logic                clk = 1'b0;
  logic                rst = 1'b1;
  logic                we = 1'b0;
  logic [AW-1:0]       waddr = '0;
  logic [DW-1:0]       wdata = '0;
  logic                start = 1'b0;
  logic [LANES*AW-1:0] addrs = '0;
  logic                busy, done;
  logic [LANES*DW-1:0] rdata;
  logic [15:0]         cycles;
  logic [LANES-1:0]    grant;
  logic [LANES*5-1:0]  lane_bank;

  banked_sram #(.MODE(MODE)) dut (
    .clk, .rst, .we, .waddr, .wdata, .start, .addrs,
    .busy, .done, .rdata, .cycles, .grant, .lane_bank
  );

  always #5 clk = ~clk;

  function automatic logic [DW-1:0] tag(input logic [AW-1:0] a);
    return {16'hA5A5, 7'b0, a};
  endfunction

  logic [AW-1:0] reqmem [0:LANES*MAXREQ-1];
  string         reqfile, tracefile;
  int            nreq, tracefd, req, errors;

  // Log every grant mid-cycle, after the arbiter has settled.
  always @(negedge clk)
    if (busy && tracefd != 0)
      for (int l = 0; l < LANES; l++)
        if (grant[l])
          $fwrite(tracefd, "%0d,%0d,%0d,%0d\n", req, cycles, l, lane_bank[l*5 +: 5]);

  initial begin
    if (!$value$plusargs("reqs=%s", reqfile)) $fatal(1, "missing +reqs=");
    if (!$value$plusargs("nreq=%d", nreq))    $fatal(1, "missing +nreq=");
    $readmemh(reqfile, reqmem);
    tracefd = 0;
    if ($value$plusargs("trace=%s", tracefile)) begin
      tracefd = $fopen(tracefile, "w");
      $fwrite(tracefd, "req,cycle,lane,bank\n");
    end

    repeat (2) @(negedge clk);
    rst = 1'b0;

    for (int a = 0; a < WORDS; a++) begin
      we = 1'b1; waddr = a[AW-1:0]; wdata = tag(a[AW-1:0]);
      @(negedge clk);
    end
    we = 1'b0;

    for (req = 0; req < nreq; req++) begin
      for (int l = 0; l < LANES; l++) addrs[l*AW +: AW] = reqmem[req*LANES + l];
      start = 1'b1;
      @(negedge clk);
      start = 1'b0;
      @(posedge done);
      @(negedge clk);

      errors = 0;
      for (int l = 0; l < LANES; l++)
        if (rdata[l*DW +: DW] !== tag(addrs[l*AW +: AW])) errors++;
      $display("RESULT req=%0d cycles=%0d errors=%0d", req, cycles, errors);
    end

    if (tracefd != 0) $fclose(tracefd);
    $finish;
  end
endmodule
