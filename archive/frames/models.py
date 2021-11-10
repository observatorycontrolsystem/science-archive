from archive.frames.utils import get_file_store_path
from django.utils.functional import cached_property
from django.contrib.postgres.fields import JSONField
import hashlib
import logging
from django.contrib.gis.db import models

from ocs_archive.storage.filestorefactory import FileStoreFactory
from ocs_archive.settings import settings as archive_settings

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
        default='',
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
        default='',
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
        default='',
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
        default=0,
        help_text="Reduction level of the frame"
    )
    RLEVEL = models.SmallIntegerField(
        default=0,
        help_text="Reduction level of the frame"
    )
    site_id = models.CharField(
        default='',
        max_length=3,
        help_text="Originating site code. Usually the 3 character airport code of the nearest airport"
    )
    SITEID = models.CharField(
        default='',
        max_length=3,
        help_text="Originating site code. Usually the 3 character airport code of the nearest airport"
    )
    telescope_id = models.CharField(
        default='',
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
        default='',
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
        default='',
        max_length=20,
        choices=OBSERVATION_TYPES,
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
        ordering = ['-observation_date']

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

    def get_header_dict(self):
        return {
            archive_settings.OBSERVATION_DATE_KEY: self.observation_date.isoformat(),
            archive_settings.OBSERVATION_DAY_KEY: self.observation_day.isoformat(),
            archive_settings.REDUCTION_LEVEL_KEY: self.reduction_level,
            archive_settings.INSTRUMENT_ID_KEY: self.instrument_id,
            archive_settings.EXPOSURE_TIME_KEY: self.exposure_time,
            archive_settings.SITE_ID_KEY: self.site_id,
            archive_settings.TELESCOPE_ID_KEY: self.telescope_id,
            archive_settings.OBSERVATION_ID_KEY: self.observation_id,
            archive_settings.PRIMARY_FILTER_KEY: self.primary_optical_element,
            archive_settings.TARGET_NAME_KEY: self.target_name,
            archive_settings.REQUEST_ID_KEY: self.request_id,
            archive_settings.CONFIGURATION_TYPE_KEY: self.configuration_type,
            archive_settings.PROPOSAL_ID_KEY: self.proposal_id,
            archive_settings.PUBLIC_DATE_KEY: self.public_date,
        }

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
    def size(self):
        path = get_file_store_path(self.frame.filename, self.frame.get_header_dict())
        file_store = FileStoreFactory.get_file_store_class()()
        return file_store.get_file_size(path)

    @cached_property
    def url(self):
        path = get_file_store_path(self.frame.filename, self.frame.get_header_dict())
        file_store = FileStoreFactory.get_file_store_class()()
        return file_store.get_url(path, self.key, expiration=3600 * 48)

    def delete_data(self):
        logger.info('Deleting version', extra={'tags': {'key': self.key, 'frame': self.frame.id}})
        path = get_file_store_path(self.frame.filename, self.frame.get_header_dict())
        file_store = FileStoreFactory.get_file_store_class()()
        file_store.delete_file(path, self.key)

    def __str__(self):
        return '{0}:{1}'.format(self.created, self.key)
