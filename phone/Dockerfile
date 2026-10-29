FROM ghcr.io/astral-sh/uv:0.7.20-python3.12-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src

# the agent handles untrusted audio and runs tools: it runs unprivileged
RUN useradd --system --uid 10001 --no-create-home app
USER app

# the venv's python directly, so no uv cache or home is needed at runtime
CMD [".venv/bin/python", "src/agent.py", "start"]
