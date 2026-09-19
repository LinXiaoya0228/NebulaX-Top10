FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and datasets
COPY . .

# Set default port for Cloud Run (overridden by Cloud Run's $PORT environment variable)
ENV PORT=8080
EXPOSE 8080

# Run Streamlit with address bound to 0.0.0.0 and port to $PORT
CMD ["sh", "-c", "streamlit run app.py --server.port=${PORT} --server.address=0.0.0.0"]
