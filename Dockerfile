# RAG Research Copilot — local-first container.
# The app talks to Ollama over its OpenAI-compatible endpoint; in docker-compose
# OLLAMA_BASE_URL points at the sibling `ollama` service.

FROM python:3.12-slim

WORKDIR /app

# Deps first for layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App + corpus + evals (the index itself lives in the ./cache volume).
COPY . .

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501', timeout=3)" || exit 1

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
