from django.db import models
from django.contrib.postgres.fields import JSONField
from pgsphere.fields import SBoxField
import hashlib
import boto3
from django.conf import settings


class Frame(models.Model):
    OBSERVATION_TYPES = (
        ('BIAS', 'BIAS'),
        ('DARK', 'DARK'),
        ('EXPERIMENTAL', 'EXPERIMENTAL'),
        ('EXPOSE', 'EXPOSE'),
        ('SKYFLAT', 'SKYFLAT'),
        ('STANDARD', 'STANDARD'),
    )
    filename = models.CharField(max_length=1000, db_index=True, unique=True)
    area = SBoxField(null=True)
    related_frames = models.ManyToManyField('self', blank=True)
    DATE_OBS = models.DateTimeField(
        db_index=True,
        null=True,
        help_text="Time of observation in UTC. FITS header: DATE-OBS",
        verbose_name="DATE-OBS"
    )
    USERID = models.CharField(
        max_length=200,
        db_index=True,
        default='',
        help_text="Textual user id of the frame. FITS header: USERID"
    )
    PROPID = models.CharField(
        max_length=200,
        db_index=True,
        default='',
        help_text="Textual proposal id. FITS header: PROPID"
    )
    INSTRUME = models.CharField(
        max_length=10,
        db_index=True,
        default='',
        help_text="Instrument used. FITS header: INSTRUME"
    )
    OBJECT = models.CharField(
        max_length=200,
        db_index=True,
        default='',
        help_text="Target object name. FITS header: OBJECT"
    )
    SITEID = models.CharField(
        default='',
        max_length=3,
        help_text="Originating site. FITS header: SITEID"
    )
    TELID = models.CharField(
        default='',
        max_length=4,
        help_text="Originating telescope. FITS header: TELID"
    )
    EXPTIME = models.DecimalField(
        null=True,
        max_digits=10,
        decimal_places=5,
        help_text="Exposure time, in seconds. FITS header: EXPTIME"
    )
    FILTER = models.CharField(
        default='',
        max_length=100,
        help_text="Filter used. FITS header: FILTER"
    )
    L1PUBDAT = models.DateTimeField(
        null=True,
        help_text="The date the frame becomes public. FITS header: L1PUBDAT"
    )
    OBSTYPE = models.CharField(
        default='',
        max_length=20,
        choices=OBSERVATION_TYPES,
        help_text="Type of observation. FITS header: OBSTYPE"
    )
    modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.filename

    @property
    def s3_key(self):
        return '/'.join((
            hashlib.sha1(self.filename.encode('utf-8')).hexdigest()[0:4],
            self.filename
        ))

    @property
    def url(self):
        """
        Returns the download URL for the latest version
        """
        return self.version_set.first().url


class Headers(models.Model):
    data = JSONField(default=dict)
    frame = models.OneToOneField(Frame)


class Version(models.Model):
    frame = models.ForeignKey(Frame)
    timestamp = models.DateTimeField(auto_now_add=True)
    key = models.CharField(max_length=32, unique=True)
    md5 = models.CharField(max_length=32, unique=True)

    class Meta:
        ordering = ['-timestamp']

    @property
    def url(self):
        client = boto3.client('s3')
        params = {
            'Bucket': settings.BUCKET,
            'Key': self.frame.s3_key,
            'VersionId': self.key
        }
        return client.generate_presigned_url('get_object', Params=params)

    def __str__(self):
        return '{0}:{1}'.format(self.timestamp, self.key)
