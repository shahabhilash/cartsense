FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

# The ML export (artifacts/export) is mounted or copied at deploy time; it is not part of the image
ENV CARTSENSE_EXPORT_DIR=/data/export
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
