FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PLUP_HOST=0.0.0.0 PORT=8000 PLUP_DB_PATH=/data/plup.sqlite3
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core gosu && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && mkdir /data && chown 10001:10001 /data
COPY web ./web
COPY server ./server
COPY entrypoint.sh ./entrypoint.sh
RUN chmod 755 ./entrypoint.sh
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
