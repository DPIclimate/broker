# syntax=docker/dockerfile:1

FROM python:3.8-slim-buster

ENV bearer_token=bad_token
ENV end_point=https://staging.farmdecisiontech.net.au

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000

CMD [ "python", "./app/main.py"]