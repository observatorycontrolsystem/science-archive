FROM python:3.8-slim AS app

# Set working directory
WORKDIR /app

# Install operating system dependencies
RUN apt-get -y update \
        && apt-get -y install gdal-bin libcfitsio-bin libpq-dev python-dev-is-python3 gcc make htop \
        && apt-get -y clean

COPY .poetry-version .

RUN pip --no-cache-dir install -r .poetry-version

COPY pyproject.toml poetry.lock ./

RUN poetry export > requirements.txt \
  && pip --no-cache-dir install -r requirements.txt

COPY . ./
