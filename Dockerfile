FROM python:3.12-slim

WORKDIR /app

# Install system deps (OR-Tools needs libstdc++)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy project metadata first (layer-cache friendly)
COPY pyproject.toml constraints.txt ./
COPY src/ ./src/

# Install the package and all dependencies (versions pinned to CI: constraints.txt)
RUN pip install --no-cache-dir -e "." -c constraints.txt

# Copy application code
COPY scripts/ ./scripts/
COPY notebooks/ ./notebooks/

# Data directory is mounted at runtime — create the mount point
RUN mkdir -p data/db

# Streamlit config: disable telemetry, set server options
RUN mkdir -p /root/.streamlit && printf \
    '[server]\nheadless = true\nport = 8501\nenableCORS = false\n\n[browser]\ngatherUsageStats = false\n' \
    > /root/.streamlit/config.toml

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

CMD ["streamlit", "run", "src/argos/ui/dashboard.py", "--server.address=0.0.0.0"]
