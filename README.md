# Verilinx

[直接下载包含前端的完整 Demo ZIP](https://raw.githubusercontent.com/SuperiorLQF/verilinx/main/downloads/verilinx-demo.zip)

基于 slang 的 SystemVerilog 模块连接 demo。单入口 filelist、顶层参数、generate、信号拼拆，以及「顶层文件即工程」。

## 启动

需要 Python 3.12+、Node.js 20.19+。在仓库根目录执行：

```sh
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 3000
```

- React 图形编辑器：`http://localhost:3000/`
- HTML 移动检视版：`http://localhost:3000/review/`
- 交互式 API 文档：`http://localhost:3000/docs`

两个前端共用同一 API，编辑状态各自独立，可以用顶层工程文件互换设计。移动端需访问主机可达或已转发的地址；手机的 localhost 是手机自身。

开发热更新：同一后端保持运行，执行 `npm --prefix frontend run dev`，Vite 转发 API 到 3000 端口。

## 先试六路示例

1. 点击「载入六路示例」。
2. 查看六路 processor generate，切换叠放和展开。
3. 输出数组同时进入分线器和 48 位向量转换组件；lane 0 对应最高字节。
4. 点击「检查设计」，查看 slang 诊断和生成 RTL。
5. 点击「导出顶层」，下载 `verilinx_top.sv`。
6. 在另一个前端「打开工程」，恢复输入源码、嵌套 filelist 原文、参数、组件、网络及布局。

导入自己的项目时，选择覆盖所有依赖的目录及一个入口 filelist。允许嵌套 `-f/-F`，路径语义交给 slang。使用相对路径；归档之外的绝对路径依赖会被拒绝。

手机不能选择目录时，可上传路径→文件文本的 JSON 包：

```sh
python scripts/bundle.py examples /tmp/verilinx-example.json
```

在 HTML 版导入 JSON 包，入口填写 `project.f`。

## 实现内容

- slang 原生 filelist 和 `--single-unit`，支持 define/undef 源文件边界。
- 顶层 parameter 每行一条，不用逗号/分号。
- 添加模块立即使用默认参数；双击修改名称、覆盖值、generate 数量。
- 顶层上下文求值，再通过保留位宽/符号/X/Z 的 `-G` 覆盖分析目标模块。
- generate 参数引用 `i`，支持各路位宽不同的独立端口。
- 标量、packed 及固定 unpacked 数组；lane 级连接。
- 顶层 IO、常量、split、concat、reshape。
- 形状、重叠驱动、必需输入检查，最终 RTL 再次交给 slang 验证。
- JSON → zlib → Base64，附 SHA-256，内嵌完整工程及源码快照。

## 首版边界

信号声明和位映射按当前顶层默认参数展开。参数修改后需在编辑器重新分析、调整适配器并重新生成；导出的 RTL 尚不是可以在外部任意改参数而自动重构布线的通用 IP。

暂不支持 interface/modport、inout/ref、动态数组、结构体端口、类型/字符串/实数参数、协议级自动连线、综合及仿真。诊断显示 slang 原始文本。浏览器策略阻止了本轮实际 GUI 交互验收；已完成后端回归、前端构建和 HTML JavaScript 语法检查。

服务用于受信任本地开发环境，尚未实现多租户认证。

## 验证

```sh
.venv/bin/python -m pytest -q
npm --prefix frontend run build
node --check review/app.js
```

详见 [开发文档](docs/DEVELOPMENT.md)：协议、架构、API、语义边界和人工验收清单。

Windows、Linux 的下载包启动命令与在线部署配置见 [运行与部署](docs/DEPLOYMENT.md)。仓库已提供 Dockerfile 和 Render Blueprint；只有托管平台确认部署成功后才视为已发布。
