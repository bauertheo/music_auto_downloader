FROM python:3.12-slim

# Install Git
RUN apt-get update && \
    apt-get install -y git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Abhängigkeiten
COPY app/ /app/
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Startskript
COPY run.sh /run.sh

CMD ["/run.sh"]

