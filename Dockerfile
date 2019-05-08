FROM python:3.6-slim

# Set working directory
WORKDIR /app

# Install operating system dependencies
RUN apt-get -y update \
        && apt-get -y install gdal-bin \
        && apt-get -y clean

# Install Python dependencies
COPY requirements.txt .
RUN pip --no-cache-dir install -r requirements.txt

# Install application code
COPY . .
