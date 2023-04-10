FROM python:3.10

WORKDIR /usr/src/app

#EXPOSE 8000

COPY requirements.txt ./


RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir -r requirements.txt

COPY basic_api.py ./
COPY db.py ./

CMD [ "uvicorn", "basic_api:app", "--host", "0.0.0.0", "--port", "8000"]
