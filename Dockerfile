FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY manage.py ./
COPY config/ ./config/
COPY menus/ ./menus/
RUN DJANGO_SECRET_KEY=collect-static-only DJANGO_ALLOWED_HOSTS=localhost DJANGO_DB_PATH=/tmp/collect.sqlite3 python manage.py collectstatic --noinput
RUN useradd --system --uid 10001 app
USER 10001
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
