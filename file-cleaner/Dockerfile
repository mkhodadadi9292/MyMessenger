FROM a_base_python:latest

WORKDIR /app

COPY . .

RUN uv add aiokafka apscheduler httpx

CMD ["uv", "run", "python", "main.py"]
