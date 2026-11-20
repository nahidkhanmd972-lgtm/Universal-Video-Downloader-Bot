
FROM python:3.11-slim

# Prevent Python buffering and bytecode files
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    DENO_INSTALL=/usr/local

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Deno JavaScript Runtime (yt-dlp EJS support)
RUN curl -fsSL https://deno.land/install.sh | sh \
    && deno --version

# Make sure Deno is available
ENV PATH="/usr/local/bin:${PATH}"

# Install Python dependencies
COPY requirements.txt .

RUN python -m pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && python -m pip install --no-cache-dir --upgrade "yt-dlp[default]"

# Copy bot source code
COPY . .

# Verify required tools
RUN ffmpeg -version \
    && ffprobe -version \
    && deno --version \
    && python -m pip show yt-dlp

# Expose application port
EXPOSE 8080

# Start Telegram Bot
CMD ["python", "bot.py"]
