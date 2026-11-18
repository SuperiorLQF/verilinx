# 下载 0.1.6

- **持续开发：[Git 克隆与热更新指南](../docs/SOURCE_DEVELOPMENT.md)**，源码位于 main 分支。
- [Linux x86_64 独立运行包（约 20 MB）](https://raw.githubusercontent.com/SuperiorLQF/verilinx/main/downloads/verilinx-linux-x86_64-0.1.6.tar.gz)
- [Linux 完整运行步骤](../docs/LINUX.md)
- [已有 Python 安装：代码更新包](https://raw.githubusercontent.com/SuperiorLQF/verilinx/main/downloads/verilinx-update-0.1.6.zip)
- [含已构建前端的源码完整包](https://raw.githubusercontent.com/SuperiorLQF/verilinx/main/downloads/verilinx-demo-0.1.6.zip)
- [最新完整源码包固定地址](https://raw.githubusercontent.com/SuperiorLQF/verilinx/main/downloads/verilinx-demo.zip)
- [发行与下载页面](https://superiorlqf.github.io/verilinx/)

开发者可以直接克隆，无需反复下载安装包：

```sh
git clone --branch main https://github.com/SuperiorLQF/verilinx.git
cd verilinx
```

修改前建议建立自己的开发分支。开发时用 Python 启动 3000 后端、Vite 启动 5173 前端，保存源码后自动更新；具体安装、启动和保留本地修改的同步方法见上方指南。

独立运行包需要 x86_64 Linux / glibc 2.31+（Ubuntu 20.04+、Debian 11+），无需安装 Python、Node.js 或 slang。解压后运行：

```sh
tar -xzf verilinx-linux-x86_64-0.1.6.tar.gz
cd verilinx-linux-x86_64
./verilinx
```

在同一台电脑浏览器打开 http://127.0.0.1:3000/ 。保持终端运行，Ctrl+C 停止。

仅保留主画布。0.1.6 强制横平竖直走线，完成连接时自动修正末段轻微错位；生成连线以输出端口名命名，重名时加实例名或编号。支持逐点手动布线：点击输出、单击放转折点、点击输入完成。Backspace 撤回，Esc 取消；选中线可以编辑转折点或重画路径。模块绝对坐标、全部走线转折点及端口布局随顶层文件保存。22 项前端、24 项后端测试和真实浏览器导出恢复验收通过。

已有 Python 安装可用更新包同步后端入口与前端，不重装环境。在原来的 verilinx 目录先 Ctrl+C 停止服务，再执行：

```sh
curl -fL https://raw.githubusercontent.com/SuperiorLQF/verilinx/main/downloads/verilinx-update-0.1.6.zip -o /tmp/verilinx-frontend-update.zip
unzip -o /tmp/verilinx-frontend-update.zip
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 3000
```

浏览器 Ctrl+Shift+R，左上角应显示 STUDIO / 0.1.6。补丁不修改工程。

源码完整 ZIP 含前端产物，无需 Node.js，仍需 Python 3.12+ 安装后端依赖。每个包都有 `.sha256` 文件，下载后可执行 `sha256sum -c <文件名>.sha256`。

`linux-release` 分支仅存放发行包和说明，不附项目开发源码。它位于公开仓库，访问仍是公开的；真正私有的后续开发需另建私有仓库。
