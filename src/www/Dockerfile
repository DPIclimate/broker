FROM python:3.10

WORKDIR /app

COPY src/www/requirements.txt requirements.txt
RUN pip install -r requirements.txt

EXPOSE 5000

CMD [ "python", "./app/main.py"]
