FROM python:3.5
MAINTAINER Austin Riba <ariba@lcogt.net>

EXPOSE 9000
ENTRYPOINT [ "/init" ]

ENV PYTHONBUFFERED 1
ENV PYTHONPATH /var/www/archive/
ENV DJANGO_SETTINGS_MODULE archive.settings

RUN apt-get update && apt-get install -y gdal-bin

COPY requirements.txt /var/www/archive/
RUN pip install -r /var/www/archive/requirements.txt --trusted-host buildsba.lco.gtn

COPY archive-deploy/init /init
COPY archive-deploy/uwsgi.ini /etc/
COPY archive-deploy/local_settings.py /var/www/archive/archive/

WORKDIR /var/www/archive/

COPY . /var/www/archive/

RUN python3 /var/www/archive/manage.py collectstatic --noinput
