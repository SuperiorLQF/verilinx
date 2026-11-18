FROM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 verilinx
COPY --chown=verilinx:verilinx backend/ backend/
COPY --chown=verilinx:verilinx examples/ examples/
COPY --chown=verilinx:verilinx scripts/run_web.py scripts/run_web.py
COPY --from=frontend --chown=verilinx:verilinx /build/frontend/dist/ frontend/dist/
USER verilinx
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
 CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','3000')+'/healthz',timeout=3)"
CMD ["python", "scripts/run_web.py"]
