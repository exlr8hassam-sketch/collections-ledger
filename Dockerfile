FROM python:3.11-slim

# Install system dependencies, curl, and Node.js 20
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    procps \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Node requirements for WhatsApp Bridge
COPY whatsapp-bridge/package*.json ./whatsapp-bridge/
WORKDIR /app/whatsapp-bridge
RUN npm install --production

# Copy application source
WORKDIR /app
COPY . .

RUN chmod +x start.sh

EXPOSE 8000 3000

ENV PORT=8000
ENV PYTHONUNBUFFERED=1

CMD ["./start.sh"]
