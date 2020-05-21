FROM python:latest

RUN mkdir /src
WORKdocker-DIR /src
COPY . /src
RUN pip install -r requirements.txt