# Use Python 3.13 slim image
FROM python:3.13-slim-bookworm

# Install uv from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Enable bytecode compilation to optimize performance
ENV UV_COMPILE_BYTECODE=1

# Copy pyproject.toml and optional uv.lock
COPY pyproject.toml uv.lock* /app/

# Install the project's dependencies
RUN if [ -f uv.lock ]; then uv sync --frozen --no-install-project; else uv sync --no-install-project; fi

# Copy the source code
COPY src /app/src

# Complete the sync to install the project itself (if applicable)
RUN if [ -f uv.lock ]; then uv sync --frozen; else uv sync; fi

# Set default execution command
CMD ["uv", "run", "python", "-m", "src.main"]
