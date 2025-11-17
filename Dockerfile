FROM python:3.6-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 2232

EXPOSE 2233

ENV HTTP_SERVICE_PORT=2232

ENV TCP_SERVICE_PORT=2233

ENV SERVER_IP=mdm.ctsdn.com

CMD ["python", "MDM.py"]
