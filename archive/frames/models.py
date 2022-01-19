from archive.frames.utils import get_s3_client
from django.utils.functional import cached_property
from django.contrib.postgres.fields import JSONField
import hashlib
import logging
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
        ('DOMEFLAT', 'DOMEFLAT'),
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
    observation_date = models.DateTimeField(
        db_index=True,
        null=True,
        help_text="Time of observation in UTC",
    )
    DATE_OBS = models.DateTimeField(
        db_index=True,
        null=True,
        help_text="Time of observation in UTC",
    )
    observation_day = models.DateField(
        null=True,
        help_text="Observing Night in YYYYMMDD",
    )
    DAY_OBS = models.DateField(
        null=True,
        help_text="Observing Night in YYYYMMDD",
    )
    proposal_id = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text="Textual proposal id"
    )
    PROPID = models.CharField(
        max_length=200,
        default='',
        blank=True,
        help_text="Textual proposal id"
    )
    instrument_id = models.CharField(
        max_length=64,
        null=True,
        help_text="Instrument used"
    )
    INSTRUME = models.CharField(
        max_length=64,
        default='',
        help_text="Instrument used"
    )
    target_name = models.CharField(
        max_length=200,
        db_index=True,
        null=True,
        blank=True,
        help_text="Target object name"
    )
    OBJECT = models.CharField(
        max_length=200,
        db_index=True,
        default='',
        blank=True,
        help_text="Target object name"
    )
    reduction_level = models.SmallIntegerField(
        null=True,
        help_text="Reduction level of the frame"
    )
    RLEVEL = models.SmallIntegerField(
        default=0,
        help_text="Reduction level of the frame"
    )
    site_id = models.CharField(
        null=True,
        max_length=3,
        help_text="Originating site code. Usually the 3 character airport code of the nearest airport"
    )
    SITEID = models.CharField(
        default='',
        max_length=3,
        help_text="Originating site code. Usually the 3 character airport code of the nearest airport"
    )
    telescope_id = models.CharField(
        null=True,
        max_length=4,
        help_text="Originating telescope 4 character code. Ex. 1m0a or 0m4b"
    )
    TELID = models.CharField(
        default='',
        max_length=4,
        help_text="Originating telescope 4 character code. Ex. 1m0a or 0m4b"
    )
    exposure_time = models.FloatField(
        null=True,
        help_text="Exposure time, in seconds"
    )
    EXPTIME = models.DecimalField(
        null=True,
        max_digits=13,
        decimal_places=6,
        help_text="Exposure time, in seconds. FITS header: EXPTIME"
    )
    primary_optical_element = models.CharField(
        null=True,
        blank=True,
        max_length=100,
        help_text="Primary Optical Element used. FITS header: FILTER"
    )
    FILTER = models.CharField(
        default='',
        blank=True,
        max_length=100,
        help_text="Primary Optical Element used. FITS header: FILTER"
    )
    public_date = models.DateTimeField(
        db_index=True,
        null=True,
        help_text="The date the frame becomes public"
    )
    L1PUBDAT = models.DateTimeField(
        db_index=True,
        null=True,
        help_text="The date the frame becomes public"
    )
    configuration_type = models.CharField(
        null=True,
        max_length=20,
        help_text="Configuration type of the observation"
    )
    OBSTYPE = models.CharField(
        default='',
        max_length=20,
        choices=OBSERVATION_TYPES,
        help_text="Configuration type of the observation"
    )
    observation_id = models.PositiveIntegerField(
        null=True,
        db_index=True,
        help_text='Unique id associated with the observation'
    )
    BLKUID = models.PositiveIntegerField(
        null=True,
        db_index=True,
        help_text='Unique id associated with the observation'
    )
    request_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text='Unique id associated with the request this observation is a part of'
    )
    REQNUM = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text='Unique id associated with the request this observation is a part of'
    )
    modified = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-DATE_OBS']

    def __str__(self):
        return self.basename

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

    def is_bpm(self):
        if self.OBSTYPE == 'BPM':
            return True
        filename = self.basename.replace('_', '-')
        if filename.startswith('bpm-') or '-bpm-' in filename or filename.endswith('-bpm'):
            return True
        return False

    def copy_to_ia(self):
        latest_version = self.version_set.first()
        client = get_s3_client()
        logger.info('Copying {} to IA storage'.format(self))
        response = client.copy_object(
            CopySource=latest_version.data_params,
            Bucket=settings.BUCKET,
            Key=latest_version.s3_daydir_key,
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

    class Meta:
        ordering = ['-created']

    @cached_property
    def data_params(self):
        return {
            'Bucket': settings.BUCKET,
            'Key': self.s3_daydir_key,
            'VersionId': self.key
        }

    @cached_property
    def size(self):
        client = get_s3_client()
        return client.head_object(Bucket=settings.BUCKET, Key=self.s3_daydir_key)['ContentLength']

    @cached_property
    def s3_daydir_key(self):
        if self.frame.DAY_OBS is None:
            # SOR files don't have the DAY_OBS, so use the DATE_OBS field:
            day_obs = self.frame.DATE_OBS.strftime('%Y%m%d')
        else:
            day_obs = self.frame.DAY_OBS.strftime('%Y%m%d')

        if self.frame.is_bpm():
            return '/'.join((
                self.frame.SITEID, self.frame.INSTRUME, 'bpm', self.frame.basename
            )) + self.extension
        else:
            data_type = 'raw' if self.frame.RLEVEL == 0 else 'processed'
            return '/'.join((
                self.frame.SITEID, self.frame.INSTRUME, day_obs, data_type, self.frame.basename
            )) + self.extension

    @cached_property
    def url(self):
        client = get_s3_client()
        return client.generate_presigned_url(
            'get_object',
            ExpiresIn=3600 * 48,
            Params=self.data_params
        )

    def delete_data(self):
        client = get_s3_client()
        logger.info('Deleting version', extra={'tags': {'key': self.key, 'frame': self.frame.id}})
        client.delete_object(**self.data_params)

    def __str__(self):
        return '{0}:{1}'.format(self.created, self.key)
