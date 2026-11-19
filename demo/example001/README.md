# Example 001 · LED 闪灯

`counter` 每计满 `PERIOD` 个时钟周期产生一次 `tick`。`led` 在同一个时钟的上升沿收到 `tick` 时翻转 `led_out`。拉低 `rst_n` 会清空计数器并熄灭 LED。

- `counter.v` 实现参数化计数器。`PERIOD` 为正整数，默认 25,000,000。
- `led.v` 实现使能翻转输出。
- `project.f` 是这两个模块的导入入口。

在 Qt 选择「示例 → LED 闪灯示例」，或在网页点击「载入 LED 闪灯示例」，即可查看接好的电路。也可以把本目录选作源码根目录，导入 `project.f`，再自行摆放并连接两个模块：

```text
clk、rst_n ──→ counter 与 led
counter.tick ──→ led.tick
led.led_out ──→ 顶层 led_out
```

默认配置在 50 MHz 时钟下每 0.5 秒翻转一次，完整闪烁周期为 1 秒。仿真时可把顶层 `PERIOD` 改成 4，释放复位后，`led_out` 会在第 4、8、12 个上升沿依次变为 1、0、1。
