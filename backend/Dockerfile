# Backend image: Python 3.12 + uv for fast, reproducible installs.
FROM python:3.12-slim

# uv: a fast Python package manager (single static binary copied from its image).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Install dependencies from pyproject.toml into the system environment.
# (--system avoids a venv; the container IS our isolation boundary.)
COPY pyproject.toml ./
RUN uv pip install --system --no-cache -r pyproject.toml

# App source is bind-mounted in docker-compose for hot-reload; this COPY makes the
# image self-contained if run without the mount.
COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
