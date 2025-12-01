FROM python:3.12-slim

# Install Git
RUN apt-get update && \
    apt-get install -y git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install streamrip globally (outside venv)
RUN pip install --no-cache-dir streamrip

# Copy app files
COPY app/ /app/
COPY requirements.txt /app/

# Create virtual environment for the Python script
RUN python3 -m venv /app/venv

# Install script dependencies in venv
RUN /app/venv/bin/pip install --no-cache-dir -r requirements.txt

# Copy start script
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]

