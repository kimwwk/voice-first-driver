FROM python:3.11-slim

WORKDIR /app

# Install OpenCode
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://opencode.ai/install | bash && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 3001
CMD ["uvicorn", "bridge:app", "--host", "0.0.0.0", "--port", "3001"]
