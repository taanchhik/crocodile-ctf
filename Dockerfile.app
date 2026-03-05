FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

RUN python -c "from database import init_db; init_db()"

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "main:app"]