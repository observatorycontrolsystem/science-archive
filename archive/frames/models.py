from django.db import models
from django.contrib.postgres.fields import JSONField
from pgsphere.fields import SBoxField


class Frame(models.Model):
    OBSERVATION_TYPES = (
        ('BIAS', 'BIAS'),
        ('DARK', 'DARK'),
        ('EXPERIMENTAL', 'EXPERIMENTAL'),
        ('EXPOSE', 'EXPOSE'),
        ('SKYFLAT', 'SKYFLAT'),
        ('STANDARD', 'STANDARD'),
    )
    filename = models.CharField(max_length=1000, db_index=True)
    area = SBoxField()
    related_frames = models.ManyToManyField('self')
    date_observed = models.DateTimeField(
        db_index=True,
        help_text="Time of observation in UTC. FITS header: DATE-OBS"
    )
    user = models.CharField(
        max_length=200,
        db_index=True,
        help_text="Textual user id of the frame. FITS header: USERID"
    )
    proposal = models.CharField(
        max_length=200,
        db_index=True,
        help_text="Textual proposal id. FITS header: PROPID"
    )
    instrument = models.CharField(
        max_length=10,
        db_index=True,
        help_text="Instrument used. FITS header: INSTRUME"
    )
    object_name = models.CharField(
        max_length=200,
        db_index=True,
        help_text="Target object name. FITS header: OBJECT"
    )
    site = models.CharField(
        max_length=3,
        help_text="Originating site. FITS header: SITEID"
    )
    telescope = models.CharField(
        max_length=4,
        help_text="Originating telescope. FITS header: TELID"
    )
    exposure_time = models.IntegerField(
        help_text="Exposure time, in MS. FITS header: EXPTIME"
    )
    filter_used = models.CharField(
        max_length=100,
        help_text="Filter used. FITS header: FILTER"
    )
    proprietary_until = models.DateTimeField(
        help_text="The date the frame becomes public. FITS header: L1PUBDAT"
    )
    observation_type = models.CharField(
        max_length=20,
        choices=OBSERVATION_TYPES,
        help_text="Type of observation. FITS header: OBSTYPE"
    )

    def __str__(self):
        return self.filename


class Headers(models.Model):
    data = JSONField()
    frame = models.OneToOneField(Frame)


class Version(models.Model):
    frame = models.ForeignKey(Frame)
    timestamp = models.DateTimeField(auto_now_add=True)
    key = models.CharField(max_length=32, unique=True)
    md5 = models.CharField(max_length=32, unique=True)
