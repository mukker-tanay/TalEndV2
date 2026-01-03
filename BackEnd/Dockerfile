FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Install system dependencies for cv parsing (if needed for opencv/pdf tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN uv pip install --system --no-cache -r requirements.txt

# Download NLTK data (since your scorer.py uses it)
RUN python -m nltk.downloader punkt punkt_tab stopwords

# Copy app code
COPY . .

# Expose port
EXPOSE 8000

# Command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]