FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project files
COPY pyproject.toml uv.lock README.md manage.py /app/
COPY hurricane /app/hurricane
COPY tests /app/tests

# Install package and dependencies
ENV UV_SYSTEM_PYTHON=1
RUN uv pip install --system -e . jinja2

ENV DJANGO_SETTINGS_MODULE=tests.testapp.settings
ENV PYTHONUNBUFFERED=1

# Migrate test database
RUN python manage.py migrate --noinput

EXPOSE 8000 8001

CMD ["python", "manage.py", "serve", "--port=8000", "--probe-port=8000"]
