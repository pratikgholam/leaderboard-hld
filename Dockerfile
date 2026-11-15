FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN pip install --upgrade pip
COPY pyproject.toml ./
RUN pip install -e .[test]

COPY . .

CMD ["uvicorn", "leaderboard_hld.main:app", "--host", "0.0.0.0","--port", "8000"]