FROM python:3.12-slim-bookworm AS base

# ENV, unlike ARG, is inherited by every stage built FROM this one, so the base
# image, the path and the workdir are written once.
ENV APP_PATH=/opt/app

WORKDIR $APP_PATH


FROM base AS builder

ENV UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    UV_COMPILE_BYTECODE=1

COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /bin/uv

# Dependencies only: the project itself is reached through PYTHONPATH, so a code
# change does not invalidate this layer.
COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project


FROM base

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=$APP_PATH/t_syncer \
    VIRTUAL_ENV=$APP_PATH/.venv \
    PATH=$APP_PATH/.venv/bin:$PATH

COPY --from=builder $APP_PATH/.venv $APP_PATH/.venv
COPY t_syncer ./t_syncer

CMD ["python", "-m", "api"]
