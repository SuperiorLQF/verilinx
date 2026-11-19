// One tick per PERIOD rising edges after reset.
module counter #(
    parameter integer PERIOD = 25_000_000
) (
    input  wire clk,
    input  wire rst_n,
    output wire tick
);
    localparam integer COUNT_WIDTH = (PERIOD > 1) ? $clog2(PERIOD) : 1;
    localparam [COUNT_WIDTH-1:0] LAST_COUNT = PERIOD - 1;

    reg [COUNT_WIDTH-1:0] count;
    assign tick = rst_n && (count == LAST_COUNT);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            count <= 0;
        else if (tick)
            count <= 0;
        else
            count <= count + 1'b1;
    end
endmodule
