FROM python:3.11-slim

# Install system dependencies (Native FFmpeg, SSL certificates, curl)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Optimize Python execution
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

# Install dependencies first for Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot source code
COPY . .

# Expose Render/Web keep-alive port
EXPOSE 8080

# Execute bot
CMD ["python", "bot.py"]