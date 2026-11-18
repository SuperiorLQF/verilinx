# Verilinx

[发行与下载页面](https://superiorlqf.github.io/verilinx/) · [Pages 启用步骤](docs/GITHUB_PAGES.md) · [Linux x86_64 独立运行包](https://raw.githubusercontent.com/SuperiorLQF/verilinx/main/downloads/verilinx-linux-x86_64-0.1.6.tar.gz)

GitHub Pages 下载页已启用，后续版本随 main 的 docs 目录更新。

Linux 独立包内置 Python 和 slang，无需安装 Python、Node.js 或 Vivado。支持 glibc 2.31+ 的 x86_64 Linux，例如 Ubuntu 20.04+、Debian 11+；解压后执行 `./verilinx`，打开 `http://127.0.0.1:3000/`。完整步骤见 [Linux 运行说明](docs/LINUX.md)。

[直接下载包含前端的完整 Demo ZIP](https://raw.githubusercontent.com/SuperiorLQF/verilinx/main/downloads/verilinx-demo.zip)

基于 slang 的 SystemVerilog 模块连接 demo。单入口 filelist、顶层参数、generate、信号拼拆，以及「顶层文件即工程」。

## 克隆源码与开发

经常修改代码请克隆 **main** 分支。需要 Git、Python 3.12+、Node.js 20.19+ 和 npm。以下以 Linux 为例：

```sh
git clone --branch main https://github.com/SuperiorLQF/verilinx.git
cd verilinx
git switch -c dev/my-work
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
npm --prefix frontend ci
```

终端一，在仓库根目录启动后端，修改 backend 自动重启：

```sh
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 3000 --reload --reload-dir backend
```

终端二，在仓库根目录启动前端，修改 frontend/src 热更新：

```sh
npm --prefix frontend run dev -- --port 5173 --strictPort
```

- 开发中的 React 画布：`http://127.0.0.1:5173/`
- 后端 API 文档：`http://127.0.0.1:3000/docs`

主画布通过 API 调用 slang，并使用顶层工程文件保存和恢复设计。移动端需访问主机可达或已转发的地址；手机的 localhost 是手机自身。

源码修改后，先在自己的开发分支提交，再执行 `git fetch origin` 和 `git merge origin/main` 合并上游更新。没有本地开发提交且工作区干净的 main 分支，可用 `git pull --ff-only`。requirements 或 package-lock 改变后才需要重新安装对应依赖。

Git 不跟踪 frontend/dist。要用 3000 单端口运行构建版，先执行 `npm --prefix frontend run build`，再启动后端；日常前端开发请访问 5173。

完整的 HTTPS/SSH 克隆、跳过发行包的精简克隆、更新合并和 ZIP 迁移步骤见 [源码开发指南](docs/SOURCE_DEVELOPMENT.md)。`linux-release` 仅含发行包，开发请选择 `main`。

## 先试六路示例

1. 点击「载入六路示例」。
2. 查看六路 processor generate，切换叠放和展开。
3. 输出数组同时进入分线器和 48 位向量转换组件；lane 0 对应最高字节。
4. 点击「检查设计」，查看 slang 诊断和生成 RTL。
5. 点击「导出顶层」，下载 `verilinx_top.sv`。
6. 点击「打开工程」，恢复输入源码、嵌套 filelist 原文、参数、组件、网络及布局。

导入自己的项目时，选择覆盖所有依赖的目录及一个入口 filelist。允许嵌套 `-f/-F`，路径语义交给 slang。使用相对路径；归档之外的绝对路径依赖会被拒绝。

## 实现内容

- slang 原生 filelist 和 `--single-unit`，支持 define/undef 源文件边界。
- 顶层 parameter 每行一条，不用逗号/分号。
- 添加模块立即使用默认参数；双击修改名称、覆盖值、generate 数量。
- 顶层上下文求值，再通过保留位宽/符号/X/Z 的 `-G` 覆盖分析目标模块。
- generate 参数引用 `i`，支持各路位宽不同的独立端口。
- 标量、packed 及固定 unpacked 数组；lane 级连接。
- 顶层 IO、常量、split、concat、reshape。
- 形状、重叠驱动、必需输入检查，最终 RTL 再次交给 slang 验证。
- 框选、多选删除、Ctrl/⌘+A 全选；六种批量对齐；拖动边缘/中心吸附，Alt 临时关闭。
- 手动正交布线：点击输出、逐点放置转折点、点击输入完成；选中连线可拖动转折点。
- 模块绝对坐标、每条线的全部转折点和端口布局都编码在顶层文件注释中，打开工程原样恢复。
- 箭头表示端口方向。按 P 切换端口布局模式，或 Shift+拖动箭头沿四边滑动，Shift+方向键微调；位置随顶层工程保存。
- JSON → zlib → Base64，附 SHA-256，内嵌完整工程及源码快照。

## 首版边界

信号声明和位映射按当前顶层默认参数展开。参数修改后需在编辑器重新分析、调整适配器并重新生成；导出的 RTL 尚不是可以在外部任意改参数而自动重构布线的通用 IP。

暂不支持 interface/modport、inout/ref、动态数组、结构体端口、类型/字符串/实数参数、协议级自动连线、综合及仿真。诊断显示 slang 原始文本。0.1.1 已在真实浏览器复现并修复空白画布，验证了示例节点/连线、generate 展开、模块新增和改参。手机端仍需人工验收。

服务用于受信任本地开发环境，尚未实现多租户认证。

## 验证

```sh
.venv/bin/python -m pytest -q
npm --prefix frontend test
npm --prefix frontend run build
```

详见 [开发文档](docs/DEVELOPMENT.md)：协议、架构、API、语义边界和人工验收清单。

Windows、Linux 的下载包启动命令与在线部署配置见 [运行与部署](docs/DEPLOYMENT.md)。仓库已提供 Dockerfile 和 Render Blueprint；只有托管平台确认部署成功后才视为已发布。
