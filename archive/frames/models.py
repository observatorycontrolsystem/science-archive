from archive.frames.utils import get_s3_client
from django.utils.functional import cached_property
from django.contrib.postgres.fields import JSONField
import hashlib
import logging
from datetime import timedelta
from django.conf import settings
from django.contrib.gis.db import models

logger = logging.getLogger()


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
        ('CATALOG', 'CATALOG'),
        ('BPM', 'BPM'),
        ('TARGET', 'TARGET'),
        ('TEMPLATE', 'TEMPLATE'),
        ('OBJECT', 'OBJECT'),
        ('TRACE', 'TRACE'),
        ('DOUBLE', 'DOUBLE')
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
        blank=True,
        help_text="Textual proposal id. FITS header: PROPID"
    )
    INSTRUME = models.CharField(
        max_length=64,
        default='',
        help_text="Instrument used. FITS header: INSTRUME"
    )
    OBJECT = models.CharField(
        max_length=200,
        db_index=True,
        default='',
        blank=True,
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
        max_digits=13,
        decimal_places=6,
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
    BLKUID = models.PositiveIntegerField(
        null=True,
        db_index=True,
        help_text='Block id from the pond. FITS header: BLKUID'
    )
    REQNUM = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text='Request id number, FITS header: REQNUM'
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

    @property
    def filename(self):
        """
        Returns the full filename for the latest version
        """
        return '{0}{1}'.format(self.basename, self.version_set.first().extension)

    def copy_to_ia(self):
        latest_version = self.version_set.first()
        bucket, s3_key = latest_version.get_bucket_and_s3_key()
        client = get_s3_client()
        logger.info('Copying {} to IA storage'.format(self))
        response = client.copy_object(
            CopySource=latest_version.data_params,
            Bucket=bucket,
            Key=s3_key,
            StorageClass='STANDARD_IA',
            MetadataDirective='COPY'
        )
        new_version = Version(
            frame=self,
            key=response['VersionId'],
            md5=response['CopyObjectResult']['ETag'].strip('"'),
            extension=latest_version.extension
        )
        latest_version.delete()
        new_version.save()
        logger.info('Saved new version: {}'.format(new_version.id))

class Headers(models.Model):
    data = JSONField(default=dict)
    frame = models.OneToOneField(Frame, on_delete=models.CASCADE)


class Version(models.Model):
    frame = models.ForeignKey(Frame, on_delete=models.CASCADE)
    key = models.CharField(max_length=32, unique=True)
    md5 = models.CharField(max_length=32, unique=True)
    extension = models.CharField(max_length=20)
    created = models.DateTimeField(auto_now_add=True)
    migrated = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created']

    @cached_property
    def data_params(self):
        bucket, s3_key = self.get_bucket_and_s3_key()
        return {
            'Bucket': bucket,
            'Key': s3_key,
            'VersionId': self.key
        }

    @cached_property
    def size(self):
        client = get_s3_client()
        bucket, s3_key = self.get_bucket_and_s3_key()
        return client.head_object(Bucket=bucket, Key=s3_key)['ContentLength']

    @cached_property
    def s3_daydir_key(self):
        if self.frame.SITEID.lower() == 'sor':
            # SOR files don't have the day_obs in their filename, so use the DATE_OBS field:
            day_obs = self.frame.DATE_OBS.isoformat().split('T')[0].replace('-', '')
        else:
            day_obs = self.frame.basename.split('-')[2]
        return '/'.join((
            self.frame.SITEID, self.frame.INSTRUME, day_obs, self.frame.basename, self.extension
        ))

    def get_bucket_and_s3_key(self):
        if self.migrated:
            return settings.NEW_BUCKET, self.s3_daydir_key
        else:
            return settings.BUCKET, self.frame.s3_key

    @cached_property
    def url(self, expiration=timedelta(hours=48)):
        client = get_s3_client()
        return client.generate_presigned_url(
            'get_object',
            ExpiresIn=int(expiration.total_seconds()),
            Params=self.data_params
        )

    def delete_data(self):
        client = get_s3_client()
        logger.info('Deleting version', extra={'tags': {'key': self.key, 'frame': self.frame.id}})
        client.delete_object(**self.data_params)

    def __str__(self):
        return '{0}:{1}'.format(self.created, self.key)
