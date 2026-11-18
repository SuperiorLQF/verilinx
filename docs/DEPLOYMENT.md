# 运行与在线部署

## 下载包和源码的区别

0.1.2 另提供无需安装 Python/Node 的 Linux x86_64 独立运行包，解压后 `./verilinx` 即可启动，要求 glibc 2.31+。完整步骤见 [Linux 运行说明](LINUX.md)。下文 Python 安装步骤针对源码 ZIP。

交付 ZIP 包含 `frontend/dist`，不需要 Node.js，需 Python 3.12+ 安装后端依赖。GitHub 源码不跟踪构建产物，从源码运行才需要 Node.js 20.19+ 和 npm 构建。

Linux 已完成运行与自动测试。Windows 依赖有对应发行版，但尚未进行 Windows 实机验收，不将它描述为已经验证的安装包。没有要求 Vivado、MATLAB 或单独安装 slang，`pyslang` 包包含编译前端。

Windows PowerShell（解压后进入 verilinx 目录）：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 3000
```

Linux：

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 3000
```

打开 `http://localhost:3000/`。从 GitHub 源码启动还需先执行 `npm --prefix frontend ci` 和 `npm --prefix frontend run build`。

## Render 部署

`Dockerfile` 用 Node 构建前端，再将前端产物、Python 服务和输入示例合并到非 root Python 镜像中。主画布和 `/api` 同源，无需配置跨域。无数据库或其他持久服务需求。

仓库中的 `render.yaml` 描述 Docker Web Service，选择 free 方案并自动生成访问密钥；服务会使用平台提供的 PORT。部署仍需要用户拥有并授权 Render 账号。Blueprint 配置存在不代表已经上线；应以平台实际返回的成功部署 URL 为准。

发布后由服务 secret store 注入 `VERILINX_ACCESS_TOKEN`（至少 24 个随机字符），启动器不接受空密钥。完整授权入口格式为 `https://<实际域名>/?access=<密钥>`。成功打开后跳转去掉查询参数，密钥转入 Secure、HttpOnly、SameSite=Strict Cookie。主画布和 API 使用该 Cookie。不要把密钥写入仓库、Docker 镜像、请求日志或公开文档。

`/healthz` 只返回 `{"ok":true}`，供托管平台探活。其余页面和 API 均需访问授权。已有本地 uvicorn 运行方式不设置该环境变量时保持本地开发行为。

该 gate 用于单人评测，不能替代多租户隔离。不要向不受信任的公众分发完整密钥链接。免费实例可能休眠和冷启动，具体额度及可用性以部署时的 Render 账号为准，不自动升级付费方案。

## 验收

1. 匿名请求 `/api/health` 返回 401；`/healthz` 返回 200。
2. 用完整链接解锁，重定向中不再带密钥；Cookie 带 Secure 和 HttpOnly。
3. 主画布、静态资源以及 API 请求均成功。
4. 载入六路示例，执行 `/api/analyze` 和 `/api/export`，由真实 slang 返回结果。
5. 从导出的顶层恢复工程，再比较输入 filelist、参数和连线。
6. 在手机浏览器实际执行上述操作。

## 当前环境的发布情况

Sites 的 Worker 运行时不能直接运行 pyslang 原生扩展。尝试直接发布临时 Cloudflare HTTPS 隧道时，隧道注册连接被环境网络拒绝，未获得可用公网链接。没有用只有页面、没有 slang 后端的静态预览代替完整部署。

GitHub Pages 用于发行下载页，不能运行 pyslang 后端。完整编辑器通过本地独立运行包启动；Render 仍为可选的在线后端部署方式。隧道失败不影响本地运行。

## 容器验证记录

早期版本已构建服务镜像，并在非 root 容器内通过主画布、匿名拒绝、健康检查、带授权的真实 slang 示例、导出和恢复测试。构建环境使用代理 CA，以 BuildKit secret 临时提供给 pip/npm；证书没有进入镜像或仓库。普通托管构建仍使用 Dockerfile 默认的 TLS 校验。

构建依赖审计仍报告 picomatch/fdir/tinyglobby/Vite 的 ReDoS 告警，`npm audit fix` 没有消除，未声称依赖审计零告警。发布运行镜像只包含构建后的静态资源和 Python 服务，不包含 Node.js、Vite 开发服务器或这些构建依赖。
