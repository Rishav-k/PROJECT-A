FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pulse_media/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY pulse_media/ .

RUN mkdir -p data/sessions logs output/images

EXPOSE 8888

CMD ["python3", "dashboard/server.py"]
