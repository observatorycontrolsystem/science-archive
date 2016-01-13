FROM python:3.5
MAINTAINER Austin Riba <ariba@lcogt.net>

RUN apt-get update && apt-get install gdal-bin

ENV PYTHONBUFFERED 1
ENV APPLICATION_ROOT /app/

RUN mkdir -p $APPLICATION_ROOT
WORKDIR $APPLICATION_ROOT
ADD requirements.txt $APPLICATION_ROOT
RUN pip install -r requirements.txt --trusted-host buildsba.lco.gtn
ADD . $APPLICATION_ROOT
