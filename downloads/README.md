# 完整 Demo 下载

[直接下载 verilinx-demo.zip](https://raw.githubusercontent.com/SuperiorLQF/verilinx/main/downloads/verilinx-demo.zip)

此包由提交 `94a2d053f04003a5b7b6b49fd00d8f3ab69e27a9` 的源码及已构建前端组成。不需要 Node.js，仍需要 Python 3.12+ 安装并运行后端。

Linux 下载：

```sh
curl -fL https://raw.githubusercontent.com/SuperiorLQF/verilinx/main/downloads/verilinx-demo.zip -o verilinx-demo.zip
unzip verilinx-demo.zip
cd verilinx
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 3000
```

如需校验，请下载相邻的 `verilinx-demo.zip.sha256` 后执行 `sha256sum -c verilinx-demo.zip.sha256`。
