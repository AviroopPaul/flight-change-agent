# syntax=docker/dockerfile:1
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /usr/local/bin/uv
RUN adduser --disabled-password --gecos "" --uid 10001 appuser
WORKDIR /home/appuser
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY *.py ./
RUN chown -R appuser /home/appuser
USER appuser
RUN uv run --no-dev python agent.py download-files
CMD ["uv", "run", "--no-dev", "python", "agent.py", "start"]
