# Build sentry Docker image
FROM python:3.13-slim AS builder

WORKDIR /app

# Install build dependencies
COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir -e .

# Runtime stage
FROM python:3.13-slim

WORKDIR /app

# Install vcgencmd dependencies (for Raspberry Pi)
# Note: vcgencmd is only available on Raspberry Pi OS
# On other systems, sentry will report 0 values for hardware metrics

COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin/sentry /usr/local/bin/sentry

# Create directories for config and data
RUN mkdir -p /root/.config/sentry /root/.local/share/sentry

# Default command
ENTRYPOINT ["sentry"]
CMD ["status"]
