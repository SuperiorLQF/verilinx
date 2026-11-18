# 下载 0.1.2

- [Linux x86_64 独立运行包（约 20 MB）](https://raw.githubusercontent.com/SuperiorLQF/verilinx/main/downloads/verilinx-linux-x86_64-0.1.2.tar.gz)
- [Linux 完整运行步骤](../docs/LINUX.md)
- [已有安装：仅更新前端](https://raw.githubusercontent.com/SuperiorLQF/verilinx/main/downloads/verilinx-ports-update-0.1.2.zip)
- [含已构建前端的源码完整包](https://raw.githubusercontent.com/SuperiorLQF/verilinx/main/downloads/verilinx-demo-0.1.2.zip)
- [最新完整源码包固定地址](https://raw.githubusercontent.com/SuperiorLQF/verilinx/main/downloads/verilinx-demo.zip)
- [发行下载页文件](../docs/index.html) / [GitHub Pages 启用步骤](../docs/GITHUB_PAGES.md)（当前等待管理员启用）

独立运行包需要 x86_64 Linux / glibc 2.31+（Ubuntu 20.04+、Debian 11+），无需安装 Python、Node.js 或 slang。解压后运行：

```sh
tar -xzf verilinx-linux-x86_64-0.1.2.tar.gz
cd verilinx-linux-x86_64
./verilinx
```

在同一台电脑浏览器打开 http://127.0.0.1:3000/ 。HTML 检视版为 http://127.0.0.1:3000/review/ 。保持终端运行，Ctrl+C 停止。

0.1.2 新增方向箭头和四边连续端口布局，改善连线反馈。拖输出到输入连线，P 切换端口布局，Shift+拖动或 Shift+方向键调整位置。20 项后端、10 项前端回归通过，并完成真实浏览器和 Debian 11 非 root 原生运行验证。

已有 Python 安装只需更新前端，不重装环境。在原来的 verilinx 目录先 Ctrl+C 停止服务，再执行：

```sh
curl -fL https://raw.githubusercontent.com/SuperiorLQF/verilinx/main/downloads/verilinx-ports-update-0.1.2.zip -o /tmp/verilinx-ports-update.zip
unzip -o /tmp/verilinx-ports-update.zip
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 3000
```

浏览器 Ctrl+Shift+R，左上角应显示 STUDIO / 0.1.2。补丁不修改工程。

源码完整 ZIP 含前端产物，无需 Node.js，仍需 Python 3.12+ 安装后端依赖。每个包都有 `.sha256` 文件，下载后可执行 `sha256sum -c <文件名>.sha256`。

`linux-release` 分支仅存放发行包和说明，不附项目开发源码。它位于公开仓库，访问仍是公开的；真正私有的后续开发需另建私有仓库。
