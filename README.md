# Las Cumbres Observatory Science Archive

This is the LCO Science Data Archive API. It uses the
[Django Rest Framework](https://www.django-rest-framework.org/api-guide/requests/)
to provide web accessible endpoints for adding and querying the metadata for frames.

## Requirements

### PostgreSQL with the PostGIS extension installed

Amazon Web Services (AWS) Relational Database Service (RDS) provides PostgreSQL
with the PostGIS extension installed. Please refer to the AWS documentation for
instructions on how to enable this extension.

For local development, you can use the following Docker image:

- <https://hub.docker.com/r/mdillon/postgis/>

### Amazon Web Services Simple Storage Service Bucket

This project depends upon an Amazon Web Services (AWS) Simple Storage Service
(S3) bucket to store data.

## Configuration

This project is configured by environment variables.

Environment Variable | Description | Default Value
--- | --- | ---
`SECRET_KEY` | Django Secret Key | `See settings.py`
`DEBUG` | Enable Django Debugging Mode | `False`
`DB_HOST` | PostgreSQL Database Hostname | `127.0.0.1`
`DB_NAME` | PostgreSQL Database Name | `archive`
`DB_USER` | PostgreSQL Database Username | `postgres`
`DB_PASS` | PostgreSQL Database Password | `postgres`
`AWS_ACCESS_KEY_ID` | AWS Access Key Id | ``
`AWS_SECRET_ACCESS_KEY` | AWS Secret Access Key | ``
`AWS_DEFAULT_REGION` | AWS Default Region | `us-west-2`
`AWS_BUCKET` | AWS S3 Bucket Name | `lcogtarchivetest`
`CACHE_LOC` | Memcached Cache Location | `memcached.archiveapi:11211`
`QUEUE_BROKER_URL` | RabbitMQ Broker | `memory://localhost`
`PROCESSED_EXCHANGE_NAME` | Archived FITS exchange name  | `archived_fits`


## Build

This project is built automatically by the [LCO Jenkins Server](http://jenkins.lco.gtn/).
Please see the [Jenkinsfile](Jenkinsfile) for further details.

## Production Deployment

This project is deployed onto the LCO Kubernetes Cluster. Please see the
[LCO Helm Charts Repository](https://github.com/LCOGT/helm-charts) for details.

## Development Environment

This is a standard Django project. You should be familiar with running Django
in a local development environment before continuing.

* Configure a PostgreSQL database with the PostGIS extension
* Configure a Memcached database (optional)
* Configure your environment variables appropriately (see above chart)
* Install Python dependencies: `pip install -r requirements.txt`
* Apply database migrations: `python manage.py migrate`
* Run the development server: `python manage.py runserver`

## Superuser Access

This project will only allow POST requests from a superuser account. A
superuser account can be created by using the following command:

```
python manage.py createsuperuser
```

The resulting user with have an authentcation token. This token can be
obtained:

```
python manage.py shell_plus
In [1]: User.objects.first().auth_token
Out[1]: <Token: 48d03ec62ce69fef68bd545a751ccb1efef689a5>
```

This is the authentication token that should be used in software that can write
to the archive, such as the Ingester.

For instructions on how to use Token Authentication, please see the Django Rest Framework's
documentation section on [Token Authentication](http://www.django-rest-framework.org/api-guide/authentication/#tokenauthentication).

## OAuth

Users can authenticate using OAuth. See the authentcation backends in the
`authentication/` app.
