FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY file_cleaner ./file_cleaner
COPY main.py ./

ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "main.py"]
