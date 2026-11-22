FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

# Install locked dependencies first for better layer caching.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev

COPY src/ ./src/

EXPOSE 8501

CMD [".venv/bin/streamlit", "run", "src/app.py", \
     "--server.address=0.0.0.0", "--server.headless=true"]
