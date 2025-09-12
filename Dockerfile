FROM python:3.12-slim-bookworm

# The installer requires curl (and certificates) to download the release archive
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates

# Download the latest installer
ADD https://astral.sh/uv/install.sh /uv-installer.sh

# Run the installer then remove it
RUN sh /uv-installer.sh && rm /uv-installer.sh

# Move uv to system-wide location so all users can access it
# RUN mv /root/.local/bin/uv /usr/local/bin/uv && \
#     chmod +x /usr/local/bin/uv

# Ensure the installed binary is on the `PATH`
ENV PATH="/root/.local/bin/:$PATH"

# Create a non-root user with home directory
# RUN groupadd -r appuser && useradd -r -g appuser -m -d /home/appuser appuser

WORKDIR /app

# Copy project files first (excluding .venv via .dockerignore)
COPY pyproject.toml .
COPY . .

# Create a non-root user and change ownership
# RUN chown -R appuser:appuser /app && \
#     mkdir -p /home/appuser/.cache && \
#     chown -R appuser:appuser /home/appuser/.cache

# # Switch to non-root user
# USER appuser

# Set up virtual environment as appuser
# ENV VIRTUAL_ENV=/app/.venv
# RUN uv venv --relocatable
# ENV PATH="/app/.venv/bin:$PATH"

# Set a longer timeout for UV package downloads
ENV UV_HTTP_TIMEOUT=120

# Install dependencies as appuser
RUN uv sync

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]