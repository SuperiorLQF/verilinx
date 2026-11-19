// Toggle on a tick using the same clock as the counter.
module led (
    input  wire tick,
    input  wire clk,
    input  wire rst_n,
    output reg  led_out
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            led_out <= 1'b0;
        else if (tick)
            led_out <= ~led_out;
    end
endmodule
