# Science Archive

![Build](https://github.com/observatorycontrolsystem/science-archive/workflows/Build/badge.svg)
[![Coverage Status](https://coveralls.io/repos/github/observatorycontrolsystem/science-archive/badge.svg)](https://coveralls.io/github/observatorycontrolsystem/science-archive)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/3ebd5b7fcff845c980f6f6a8bb4f7ab9)](https://www.codacy.com/gh/observatorycontrolsystem/science-archive?utm_source=github.com&utm_medium=referral&utm_content=observatorycontrolsystem/science-archive&utm_campaign=Badge_Grade)

An application providing an API to save, retrieve, and view an observatory's science data. The data files themselves 
are stored in AWS S3, with certain metadata for each file stored in a database for easy querying and filtering.

## Prerequisites

Optional prerequisites can be skipped for reduced functionality.

-   Python >= 3.6
-   PostgreSQL with the PostGIS extension installed
-   An AWS S3 bucket with read/write privileges and versioning enabled
-   System dependencies to install the [psycopg2](https://pypi.org/project/psycopg2/) package
-   (Optional) RabbitMQ
-   (Optional) Memcached

## Configuration

Users can use Oauth for authentication. The authentication server for the science archive is the [observation portal](https://github.com/observatorycontrolsystem/observation-portal).

This project can be configured to use just a single database, or queries can be routed to separate endpoints of a database cluster such that read operations are routed to replicas and write operations are routed to the main writer database.

This project is configured using environment variables.

|                 | Variable                     | Description                                                                                                                                                                                                                          | Default                         |
| --------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------- |
| General         | `SECRET_KEY`                 | Django Secret Key                                                                                                                                                                                                                    | _random string_                 |
|                 | `DEBUG`                      | Enable Django Debugging Mode                                                                                                                                                                                                         | `False`                         |
|                 | `CACHE_LOC`                  | Memcached Cache Location                                                                                                                                                                                                             | `memcached.archiveapi:11211`    |
| Database        | `DB_HOST`                    | PostgreSQL Database Hostname for the writer endpoint                                                                                                                                                                                 | `127.0.0.1`                     |
|                 | `DB_HOST_READER`             | PostgreSQL Database Hostname for the reader endpoint. This can be set to the same value as `DB_HOST` if a cluster is not being used.                                                                                                 | `127.0.0.1`                     |
|                 | `DB_NAME`                    | PostgreSQL Database Name                                                                                                                                                                                                             | `archive`                       |
|                 | `DB_USER`                    | PostgreSQL Database Username                                                                                                                                                                                                         | `postgres`                      |
|                 | `DB_PASS`                    | PostgreSQL Database Password                                                                                                                                                                                                         | `postgres`                      |
| AWS             | `AWS_ACCESS_KEY_ID`          | AWS Access Key Id                                                                                                                                                                                                                    | _empty string_                  |
|                 | `AWS_SECRET_ACCESS_KEY`      | AWS Secret Access Key                                                                                                                                                                                                                | _empty string_                  |
|                 | `AWS_DEFAULT_REGION`         | AWS Default Region                                                                                                                                                                                                                   | `us-west-2`                     |
|                 | `AWS_BUCKET`                 | AWS S3 Bucket Name                                                                                                                                                                                                                   | `lcogtarchivetest`              |
|                 | `S3_ENDPOINT_URL`            | Endpoint url for connecting to s3. This can be modified to connect to a local instance of s3.                                                                                                                                        | `http://s3.us-west-2.amazonaws.com`              |
| Post-processing | `PROCESSED_EXCHANGE_ENABLED` | Enable post-processing. When `True`, details of a newly ingested image are sent to a RabbitMQ exchange. This is useful for e.g. data pipelines that need to know whenever there is a new image available. Set to `False` to disable. | `True`                          |
|                 | `QUEUE_BROKER_URL`           | RabbitMQ Broker                                                                                                                                                                                                                      | `memory://localhost`            |
|                 | `PROCESSED_EXCHANGE_NAME`    | Archived FITS exchange name                                                                                                                                                                                                          | `archived_fits`                 |
| Expire Guide Frames         | `GUIDE_CAMERAS_TO_PERSIST`                 | comma delimited list of guide camera names to exclude from expiring after 1 year                                                                                                                                                                                                                     | _empty string_               |
| Oauth           | `OAUTH_CLIENT_ID`            | Oauth client ID                                                                                                                                                                                                                      | _empty string_                  |
|                 | `OAUTH_CLIENT_SECRET`        | Oauth client secret                                                                                                                                                                                                                  | _empty string_                  |
|                 | `OAUTH_TOKEN_URL`            | Observation portal Oauth token URL                                                                                                                                                                                                   | `http://localhost/o/token/`     |
|                 | `OAUTH_PROFILE_URL`          | Observation portal profile URL                                                                                                                                                                                                       | `http://localhost/api/profile/` |

## Local Development

### **Set up the S3 bucket**

Please refer to the [S3 documentation](https://aws.amazon.com/s3/) for how to set up a bucket with read/write access.

### **Set up a [virtual environment](https://docs.python.org/3/tutorial/venv.html)**

Using a virtual environment is highly recommended. Run the following commands from the base of this project. `(env)`
is used to denote commands that should be run using your virtual environment. Note that [the system dependencies of
the psycopg2 PyPI package](https://www.psycopg.org/docs/install.html#install-from-source) must be installed at this
point.

    python3 -m venv env
    source env/bin/activate
    (env) pip install -r requirements.txt

### **Set up the database**

This example uses a [PostgreSQL Docker Image](https://hub.docker.com/r/mdillon/postgis/) that already has PostGIS installed. Make sure that the options that you use to set up your database correspond with your configured database settings.

    docker run --name archive-postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=archive -p5432:5432 -d mdillon/postgis

After creating the database, migrations must be applied to set up the tables in the database.

    (env) python manage.py migrate

### **Run the tests**

    (env) python manage.py test

### **Run the science archive**

    (env) python manage.py runserver

The science archive should now be accessible from <http://127.0.0.1:8000>

## Adding data

Only superusers can ingest data into the science archive. To create a superuser, run the following command and follow the steps:

    (env) python manage.py createsuperuser

Obtain the resulting authentication token which can then be used by the [ingester](https://github.com/observatorycontrolsystem/ingester). 

    python manage.py shell_plus
    In [1]: User.objects.first().auth_token
    Out[1]: <Token: 48d03ec62ce69fef68bd545a751ccb1efef689a5>
