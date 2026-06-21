FROM mcr.microsoft.com/playwright/python:v1.60.0-noble

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY knowledge ./knowledge
COPY src ./src

RUN python -m pip install --upgrade pip \
    && python -m pip install .

EXPOSE 8000

CMD ["uvicorn", "rtbdi_assistant.api:app", "--host", "0.0.0.0", "--port", "8000"]
