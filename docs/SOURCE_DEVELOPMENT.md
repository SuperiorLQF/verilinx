# 克隆源码与持续开发

经常修改代码时，使用 `main` 分支的 Git 源码。`linux-release` 分支仅存放运行包和说明；开发入口是 `main`。

以下命令以 Linux 为例，需要 Git、Python 3.12+、Node.js 20.19+ 和 npm。Python 的 venv 模块也需要可用。`pyslang` 已包含 slang，不需要安装 Vivado 或另行编译 slang。

## 1. 克隆并建立自己的开发分支

```sh
git clone --branch main https://github.com/SuperiorLQF/verilinx.git
cd verilinx
git switch -c dev/my-work
```

也可以使用已配置 GitHub SSH 密钥的地址：

```sh
git clone --branch main git@github.com:SuperiorLQF/verilinx.git
```

公开仓库通过 HTTPS 克隆不需要登录；推送修改需要有仓库写入权限，或先 fork 到自己的账号。

### 可选：跳过发行包及其历史内容

仓库的 downloads 目录包含历史发行包。只开发源码时，可以改用以下方式克隆；顶层 README、requirements 等文件仍会保留：

```sh
git clone --filter=blob:none --sparse --branch main https://github.com/SuperiorLQF/verilinx.git
cd verilinx
git sparse-checkout set backend frontend review examples scripts tests docs
git switch -c dev/my-work
```

需要完整工作区时可执行 `git sparse-checkout disable`。普通克隆与精简克隆任选一种，不要在同一目录重复克隆。

## 2. 首次安装开发依赖

在克隆后的 verilinx 根目录执行：

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
npm --prefix frontend ci
```

确认版本可以使用 `python3.12 --version`、`node --version`、`npm --version`。这里不要求激活虚拟环境，所有 Python 命令都明确使用 `.venv/bin/python`。

## 3. 开发模式：两个终端，自动刷新

终端一，在仓库根目录启动后端：

```sh
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 3000 --reload --reload-dir backend
```

终端二，也在仓库根目录启动前端：

```sh
npm --prefix frontend run dev -- --port 5173 --strictPort
```

在运行这些命令的同一台电脑浏览器打开 **http://127.0.0.1:5173/**。修改 `frontend/src` 后由 Vite 热更新；修改 `backend` 后由 uvicorn 自动重启。两端都保持终端运行，Ctrl+C 停止。

开发前端的 `/api` 和 `/review` 请求由 Vite 转发到 `127.0.0.1:3000`。HTML 检视版可以访问 http://127.0.0.1:5173/review/ 或 http://127.0.0.1:3000/review/。

**开发时主画布访问 5173。** Git 仓库不跟踪 `frontend/dist`；没有执行构建时，3000 根路径只会提示先构建前端，或显示此前构建的旧页面。修改源码不会自动更新 3000 上的 dist。

如果端口已被旧实例占用，先关闭该实例。前端使用 `--strictPort`，避免静默改到另一个端口；如果要修改后端端口，需要同步修改 `frontend/vite.config.ts` 的两个代理目标。

手机访问开发机器时，需要使用机器的实际局域网 IP，且手机能连到该机器。手机自身的 `127.0.0.1` 不指向你的 Linux 或云环境。远程环境则需要平台提供的有效端口转发入口。

## 4. 持续修改和同步上游

先在自己的 `dev/my-work` 分支保存修改：

```sh
git status
git add -u
git commit -m "保存本地开发修改"
```

`git add -u` 只暂存已跟踪文件的修改。新建的源文件需要额外执行 `git add 文件路径`；提交前用 `git diff --cached` 检查内容。自己的 RTL 工程、密钥和本地配置应单独保存，不要误提交。

再拉取并合并最新 main：

```sh
git fetch origin
git merge origin/main
```

这会保留本地开发提交。若有冲突，Git 会列出文件，需要编辑解决后 `git add` 并完成合并；如果暂时不想合并，可在这次合并尚未完成时执行 `git merge --abort`。不要用 `git reset --hard` 覆盖尚未保存的工作。

如果只是跟踪 main，从未做过本地开发提交，可以在工作区干净时使用 `git pull --ff-only`。有本地开发提交时，按上面的开发分支流程同步。

依赖文件更新后再安装对应依赖：requirements 更新时执行 `.venv/bin/python -m pip install -r requirements-dev.txt`；前端 package-lock 更新时执行 `npm --prefix frontend ci`。仅修改普通源码通常不需要重新安装依赖。安装后重启开发服务。

## 5. 构建后用 3000 单端口运行

要检查构建后的页面，先停止开发后端，再执行：

```sh
npm --prefix frontend run build
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 3000
```

此时打开 http://127.0.0.1:3000/。后续前端改动需要重新执行 build；日常开发继续使用 5173 热更新更方便。

## 6. 检查与代码位置

```sh
npm --prefix frontend test
npm --prefix frontend run build
.venv/bin/python -m pytest -q
node --check review/app.js
```

| 目录 | 内容 |
| --- | --- |
| frontend/src | React 主画布、端口、手动布线与布局 |
| backend | FastAPI、slang 分析、RTL 生成和工程编码 |
| review | 共用后端的独立 HTML 检视客户端 |
| examples | 示例 RTL 与嵌套 filelist |
| tests | 后端回归 |
| docs/DEVELOPMENT.md | 架构、数据格式和实现边界 |

## 已经下载 ZIP，如何迁移

先备份当前源码修改和顶层 `.sv` 工程文件。用 `git clone ... verilinx-dev` 克隆到一个新目录，再把自己实际修改过的源文件复制进去，用 `git diff` 核对并提交。不要把旧目录的 `.git`、`.venv`、`node_modules` 或构建产物 `frontend/dist` 覆盖到新目录。ZIP 解压目录本身没有 Git 历史，不能直接当作已经克隆的仓库执行 git pull。
