FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    WORKSPACES_ROOT=/workspaces \
    ALLOWED_COMMANDS=python,python3,pytest,npm,node,yarn,pnpm,ruff,tsc,go,cargo

RUN apt-get update \
    && apt-get install -y --no-install-recommends git nodejs npm ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./

RUN groupadd --gid 10001 autodev \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin autodev \
    && mkdir -p /workspaces /tmp \
    && chown 10001:10001 /workspaces /tmp /srv

USER 10001:10001
EXPOSE 8010

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8010/health', timeout=3)"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8010", "--no-access-log"]
