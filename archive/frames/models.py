from archive.frames.utils import get_s3_client
from django.utils.functional import cached_property
from django.contrib.postgres.fields import JSONField
import hashlib
from django.conf import settings
from django.contrib.gis.db import models


class Frame(models.Model):
    OBSERVATION_TYPES = (
        ('BIAS', 'BIAS'),
        ('DARK', 'DARK'),
        ('EXPERIMENTAL', 'EXPERIMENTAL'),
        ('EXPOSE', 'EXPOSE'),
        ('SKYFLAT', 'SKYFLAT'),
        ('STANDARD', 'STANDARD'),
        ('TRAILED', 'TRAILED'),
        ('GUIDE', 'GUIDE'),
        ('SPECTRUM', 'SPECTRUM'),
        ('ARC', 'ARC'),
        ('LAMPFLAT', 'LAMPFLAT'),
    )
    basename = models.CharField(max_length=1000, db_index=True, unique=True)
    area = models.PolygonField(geography=True, spatial_index=True, null=True, blank=True)
    related_frames = models.ManyToManyField('self', blank=True)
    DATE_OBS = models.DateTimeField(
        db_index=True,
        null=True,
        help_text="Time of observation in UTC. FITS header: DATE-OBS",
        verbose_name="DATE-OBS"
    )
    PROPID = models.CharField(
        max_length=200,
        default='',
        help_text="Textual proposal id. FITS header: PROPID"
    )
    INSTRUME = models.CharField(
        max_length=10,
        default='',
        help_text="Instrument used. FITS header: INSTRUME"
    )
    OBJECT = models.CharField(
        max_length=200,
        db_index=True,
        default='',
        help_text="Target object name. FITS header: OBJECT"
    )
    RLEVEL = models.SmallIntegerField(
        default=0,
        help_text="Reduction level of the frame"
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
        decimal_places=3,
        help_text="Exposure time, in seconds. FITS header: EXPTIME"
    )
    FILTER = models.CharField(
        default='',
        max_length=100,
        help_text="Filter used. FITS header: FILTER"
    )
    L1PUBDAT = models.DateTimeField(
        db_index=True,
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
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-DATE_OBS']

    def __str__(self):
        return self.basename

    @cached_property
    def s3_key(self):
        return '/'.join((
            hashlib.sha1(self.basename.encode('utf-8')).hexdigest()[0:4],
            self.basename
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
    key = models.CharField(max_length=32, unique=True)
    md5 = models.CharField(max_length=32, unique=True)
    extension = models.CharField(max_length=20)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created']

    @cached_property
    def url(self):
        client = get_s3_client()
        params = {
            'Bucket': settings.BUCKET,
            'Key': self.frame.s3_key,
            'VersionId': self.key
        }
        return client.generate_presigned_url('get_object', Params=params)

    @cached_property
    def size(self):
        client = get_s3_client()
        params = {
            'Bucket': settings.BUCKET,
            'Key': self.frame.s3_key,
            'VersionId': self.key
        }
        return client.head_object(**params)['ContentLength']

    def __str__(self):
        return '{0}:{1}'.format(self.created, self.key)
