FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot ./bot

# Данные кладем на том, иначе при редеплое база обнулится.
ENV DB_PATH=/data/bot.db
VOLUME ["/data"]

EXPOSE 8080

CMD ["python", "-m", "bot"]
