# GitHub Pages 下载页

下载页文件已经提交到 `main` 分支的 `docs/index.html`，包含 Linux 独立包、前端补丁、源码包下载链接及运行说明。主仓库与 Linux 发行分支已经上传，下载链接可以直接使用。

管理员已完成启用，站点 https://superiorlqf.github.io/verilinx/ 已验证返回 HTTP 200。当前 GitHub 集成仍无 Pages 配置权限；后续更新只需提交 main 的 docs 目录，无需重新开启。

如需重新配置，仓库管理员在 GitHub 打开 `SuperiorLQF/verilinx`，按以下步骤启用：

1. 打开 **Settings → Pages**。
2. 在 **Build and deployment → Source** 选择 **Deploy from a branch**。
3. Branch 选择 **main**，目录选择 **/docs**。
4. 点击 **Save**，等待 GitHub 完成构建。
5. 以 Pages 设置页实际显示的访问地址和部署成功状态为准，再打开网站验证下载按钮。

站点地址为 `https://superiorlqf.github.io/verilinx/`，在部署成功前该地址可能返回 404。启用后，后续提交到 main 的 docs 目录会自动更新页面。

Pages 只提供静态发行下载页。完整编辑器、HTML 检视客户端和 slang 后端在 Linux 独立程序内运行，使用说明见 [LINUX.md](LINUX.md)。
