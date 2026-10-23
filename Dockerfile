FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HARKTECH_BACKEND=https://harktech.co.uk

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py run_local.py ./

RUN useradd --create-home --uid 10001 mcp
USER mcp

# stdio by default; pass --http for streamable HTTP on port 8003 (/mcp).
EXPOSE 8003
ENTRYPOINT ["python", "run_local.py"]
