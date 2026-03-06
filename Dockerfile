FROM python:3.12-slim

WORKDIR /app

# Install deps first for layer caching
COPY pyproject.toml .
RUN pip install --no-cache-dir \
    "fastapi>=0.115" \
    "uvicorn[standard]>=0.34" \
    "aiosqlite>=0.20" \
    "httpx>=0.28" \
    "cmudict>=1.0"

# Copy application code
COPY app/ app/
COPY static/ static/

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
