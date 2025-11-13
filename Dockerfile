FROM python:3.6-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 2232

CMD ["python", "MDM.py"]
