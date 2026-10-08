FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ATLAS_ROOT=/app
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY app.py ./
COPY config ./config
COPY docs ./docs
COPY .streamlit ./.streamlit

# Les données réelles ne sont PAS dans l'image : les monter en lecture seule
#   docker run -p 8501:8501 -v "$(pwd)/data/processed:/app/data/processed:ro" atlas-hympyr
RUN mkdir -p /app/data/processed && useradd --system --no-create-home atlas && chown -R atlas /app
USER atlas

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8501/_stcore/health', timeout=3)"
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
