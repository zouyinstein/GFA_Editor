FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    GFA_EDITOR_DATA_DIR=/data/gfa-editor

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        minimap2 \
        ncbi-blast+ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY frontend /app/frontend
COPY examples /app/examples

RUN mkdir -p "$GFA_EDITOR_DATA_DIR"

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
