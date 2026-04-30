FROM python:3.11-slim

WORKDIR /app

COPY web/requirements.txt web/requirements.txt
RUN pip install --no-cache-dir -r web/requirements.txt

COPY . .

WORKDIR /app/web

ENV PORT=8080
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

CMD sh -c "streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT}"
