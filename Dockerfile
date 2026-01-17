# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv

RUN python -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY scripts/prefetch_parsers.py /tmp/prefetch_parsers.py
RUN pip install --no-compile .
RUN python /tmp/prefetch_parsers.py /opt/forgemcp-parsers

FROM python:3.12-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FORGEMCP_ROOT=/workspace \
    FORGEMCP_TREE_SITTER_CACHE=/opt/forgemcp-parsers

RUN apt-get update \
    && apt-get install --yes --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 forge \
    && useradd --uid 10001 --gid forge --create-home --shell /usr/sbin/nologin forge

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder --chown=10001:10001 /opt/forgemcp-parsers /opt/forgemcp-parsers

WORKDIR /workspace
USER 10001:10001

ENTRYPOINT ["forge"]
CMD ["--help"]
