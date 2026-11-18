# Demo 下载

- [完整 0.1.1 运行包](https://raw.githubusercontent.com/SuperiorLQF/verilinx/main/downloads/verilinx-demo-0.1.1.zip)
- [已有安装的画布修复补丁](https://raw.githubusercontent.com/SuperiorLQF/verilinx/main/downloads/verilinx-canvas-fix-0.1.1.zip)
- [最新完整包固定地址](https://raw.githubusercontent.com/SuperiorLQF/verilinx/main/downloads/verilinx-demo.zip)

0.1.1 修复示例和新增节点都不显示的问题，已通过实际浏览器操作和 4 项前端、18 项后端回归。

完整包包含源码提交 `9021171025813c510d9397f24211424c05e6a171` 及已构建前端，不需要 Node.js，仍需要 Python 3.12+ 安装并运行后端。

已有安装可以只更新前端，不重装依赖：先 Ctrl+C 停止服务，然后在原来的 verilinx 目录执行：

```sh
curl -fL https://raw.githubusercontent.com/SuperiorLQF/verilinx/main/downloads/verilinx-canvas-fix-0.1.1.zip -o /tmp/verilinx-canvas-fix.zip
unzip -o /tmp/verilinx-canvas-fix.zip
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 3000
```

浏览器 Ctrl+Shift+R 强刷，确认左上角显示 STUDIO / 0.1.1。补丁不修改保存的顶层工程。

每个下载包旁都有 `.sha256` 文件，可使用 `sha256sum -c` 校验。
