FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AGENTCOST_DB=/data/agentcost.db

WORKDIR /app

# dependencies first, so code changes don't bust the pip cache layer
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py db.py pricing.py seed.py ./

# SQLite lives on a volume, not inside the image
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/stats', timeout=2).status == 200 else 1)"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
