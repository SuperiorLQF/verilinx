# 下载 0.1.3

- [Linux x86_64 独立运行包（约 20 MB）](https://raw.githubusercontent.com/SuperiorLQF/verilinx/main/downloads/verilinx-linux-x86_64-0.1.3.tar.gz)
- [Linux 完整运行步骤](../docs/LINUX.md)
- [已有安装：仅更新前端](https://raw.githubusercontent.com/SuperiorLQF/verilinx/main/downloads/verilinx-arrange-update-0.1.3.zip)
- [含已构建前端的源码完整包](https://raw.githubusercontent.com/SuperiorLQF/verilinx/main/downloads/verilinx-demo-0.1.3.zip)
- [最新完整源码包固定地址](https://raw.githubusercontent.com/SuperiorLQF/verilinx/main/downloads/verilinx-demo.zip)
- [发行与下载页面](https://superiorlqf.github.io/verilinx/)

独立运行包需要 x86_64 Linux / glibc 2.31+（Ubuntu 20.04+、Debian 11+），无需安装 Python、Node.js 或 slang。解压后运行：

```sh
tar -xzf verilinx-linux-x86_64-0.1.3.tar.gz
cd verilinx-linux-x86_64
./verilinx
```

在同一台电脑浏览器打开 http://127.0.0.1:3000/ 。HTML 检视版为 http://127.0.0.1:3000/review/ 。保持终端运行，Ctrl+C 停止。

0.1.3 新增框选、多选删除、全选、六种批量对齐和拖动自动吸附。空白处拖动框选，Delete 删除，Ctrl/⌘+A 全选；多选后点击上方对齐按钮。Alt 临时关闭吸附，Space+拖动平移。20 项后端、15 项前端回归通过，并完成真实浏览器和 Debian 11 非 root 原生运行验证。

已有 Python 安装只需更新前端，不重装环境。在原来的 verilinx 目录先 Ctrl+C 停止服务，再执行：

```sh
curl -fL https://raw.githubusercontent.com/SuperiorLQF/verilinx/main/downloads/verilinx-arrange-update-0.1.3.zip -o /tmp/verilinx-arrange-update.zip
unzip -o /tmp/verilinx-arrange-update.zip
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 3000
```

浏览器 Ctrl+Shift+R，左上角应显示 STUDIO / 0.1.3。补丁不修改工程。

源码完整 ZIP 含前端产物，无需 Node.js，仍需 Python 3.12+ 安装后端依赖。每个包都有 `.sha256` 文件，下载后可执行 `sha256sum -c <文件名>.sha256`。

`linux-release` 分支仅存放发行包和说明，不附项目开发源码。它位于公开仓库，访问仍是公开的；真正私有的后续开发需另建私有仓库。
