FROM python:3.12-slim AS build
RUN pip install --no-cache-dir uv==0.12.2
WORKDIR /srv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

FROM python:3.12-slim
RUN useradd --create-home --uid 10001 kalki
WORKDIR /srv
COPY --from=build /srv/.venv ./.venv
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
ENV PATH="/srv/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER kalki
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
