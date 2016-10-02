LCOGT Science Archive
=====================

This is the database api for the lcogt science archive. It uses django rest framework
to provide endpoints for adding and querying the metadata for frames.

Requirements
------------

### Postgresql with PostGIS installed.

For development, docker is reccommended. Check out the [pg-postgis](http://git.lco.gtn/projects/DOC/repos/pg-postgis/browse/Dockerfile) docker project. Building this image will provide you with a postgresql databse with everything you need to run the archive.

To build the image:
`$ docker build -t docker.lcogt.net/pg-postgis .`

To run the database:
`$ docker run -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d docker.lcogt.net/pg-postgis`

Now we need to create the archive database and install the postgis extension to it:

`$ createdb -Upostgres archive`
`$ psql -Upostgres archive -c "CREATE EXTENSION postgis"`

The database should be setup now. The defaults contained in `settings.py` are described in the next section, and should be sufficient for most development work.


### Credentials for an Amazon S3 bucket.
The archive makes heavy use of the [boto3](https://boto3.readthedocs.io/en/latest/) library for interfacing with Amazon S3. Boto3 automatically reads specific environmental values, described in the next section.


Setup
-----

First make sure you have a postgresql database with the postgis extension installed
on the database you would like to use. `settings.py` uses these defaults, but they
can be overwritten using environmental variables:

        'NAME': os.getenv('DB_NAME', 'archive'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASS', 'postgres'),
        'HOST': os.getenv('DB_HOST', '127.0.0.1'),

You will also need these environmental variables set for Amazon credentials:

    AWS_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY
    AWS_DEFAULT_REGION

The rest is standard Django. Run `pip install -r requirements.txt --trusted-host buildsba`
to install the requirements. `./manage.py migrate` to set up the database. `./manage.py runserver`
to start the development server.


Superuser
---------

The archive will only allow POSTS from a superuser account. Create one using:

`./manage.py createsuperuser`

The resulting user with have an authentcation token. This token can be obtained:

    ./manage.py shell_plus
    In [1]: User.objects.first().auth_token
    Out[1]: <Token: 48d03ec62ce69fef68bd545a751ccb1efef689a5>

This is the auth token that should be used in software that can write to the archive, like
the ingester. See [Django Rest Framework section on Token Auth](http://www.django-rest-framework.org/api-guide/authentication/#tokenauthentication) for how to use it.


OAuth
-----

Users can authenticate using oauth. See the authentcation backends in the authentication/ app.