module array_pass #(parameter int WIDTH=8, parameter int LANES=6)(
    input logic [WIDTH-1:0] data_in [0:LANES-1],
    output logic [WIDTH-1:0] data_out [0:LANES-1]
);
    assign data_out = data_in;
endmodule
