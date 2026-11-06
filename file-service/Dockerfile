FROM a_base_python:latest

WORKDIR /app

COPY . .

RUN uv add mutagen pillow python-multipart

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]