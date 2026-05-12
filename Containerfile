# Available tags: latest, 3.14.4, 3.14, 3
ARG PYTHON_TAG=3.14.4-builder
FROM registry.access.redhat.com/hi/python:${PYTHON_TAG}

WORKDIR /app
USER root

COPY pyproject.toml /app/pyproject.toml

RUN pip install --no-cache-dir uv && \
    uv venv /app/.venv && \
    uv pip install --python /app/.venv/bin/python -r pyproject.toml && \
    mkdir -p /app/.cache && chown -R 65532:root /app/.cache
USER 65532

COPY deep_agent /app/deep_agent
COPY config /app/config
COPY aegra.json /app/aegra.json

ENV PYTHONPATH=/app

EXPOSE 5002
CMD ["/app/.venv/bin/aegra", "serve", "--host", "0.0.0.0", "--port", "5002"]
