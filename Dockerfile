FROM ghcr.io/astral-sh/uv:0.10.12@sha256:72ab0aeb448090480ccabb99fb5f52b0dc3c71923bffb5e2e26517a1c27b7fec AS uv
FROM python:3.13-slim-bookworm@sha256:ed86c82274b3c69b52fb5820f358f0bd7df0b603332063cb5c6e32bd220c3e6e
COPY --from=uv /uv /usr/local/bin/uv
ENV HOME=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_PYTHON_DOWNLOADS=never PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY common_thread ./common_thread
COPY crm ./crm
COPY templates ./templates
COPY manage.py ./
COPY scripts/gunicorn.conf.py ./gunicorn.conf.py
RUN APP_ENV=test DATABASE_URL=postgresql://build:unused@localhost/build DJANGO_SECRET_KEY=build-only-placeholder uv run --no-sync python manage.py collectstatic --noinput
RUN mkdir -p staticfiles && useradd --uid 10001 --create-home app
USER 10001:10001
EXPOSE 8000
STOPSIGNAL SIGTERM
CMD ["sh", "-c", "exec gunicorn --config gunicorn.conf.py common_thread.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 30 --graceful-timeout 25 --access-logfile /dev/null --error-logfile -"]
