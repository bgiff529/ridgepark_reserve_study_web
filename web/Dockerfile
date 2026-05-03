FROM python:3.11-slim

WORKDIR /app

COPY web/requirements.txt web/requirements.txt
RUN pip install --no-cache-dir -r web/requirements.txt

COPY . .

WORKDIR /app/web

ENV PORT=8080

CMD sh -c "shiny run --host 0.0.0.0 --port ${PORT} app.py"
