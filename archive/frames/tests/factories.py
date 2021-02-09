import factory
import factory.fuzzy
import random
import datetime
import json
import os
from archive.frames.models import Frame, Version, Headers
from django.utils import timezone
from pytz import UTC


INSTRUMENTS = (
    'ef01', 'ef02', 'ef03', 'ef04', 'ef06', 'ef07',
    'ef08', 'ef09', 'ef10', 'ef12',
    'efXX', 'em01', 'fl01', 'fl03', 'fl04', 'floyds01',
    'floyds02', 'fs02', 'fs03', 'kb01', 'kb10', 'kb11',
    'kb12', 'kb14', 'kb15', 'kb16', 'kb18', 'kb20',
    'kb21', 'kb22', 'kb31', 'kb34', 'kb37', 'kb40',
    'kb42', 'kb47', 'kb70', 'kb71', 'kb74', 'kb75',
    'kb76', 'kb78', 'kb79', 'kb80', 'kb81', 'kb93',
    'kbXX', 'tn22',
)

FILTERS = (
    'air', 'ND', 'up', 'gp', 'rp', 'ip', 'zs', 'Y', 'w',
    '150um-Pinhole', '400um-Pinhole', 'U', 'B', 'V', 'R',
    'I', 'B', '*NDV', '*NDR', '*NDI', '*ND',
)

SITES = (
    'BPL', 'COJ', 'CPT', 'ELP', 'LSC', 'OGG', 'SQA',
    'TFN', 'TST',
)

TELESCOPES = (
    '1m0a', '2m0a', '0m4a', '0m8a',
)

EXTENSIONS = (
    't00', 'e10', 'cat', 'g00', 's10', 'x00',
    'f00', 'd00', 'e00', 'e90', 'b00', 's00'
)

FORMATS = (
    'fits', '.fits.fz'
)

OBSERVATION_TYPES = (
    'BIAS', 'DARK', 'EXPERIMENTAL', 'EXPOSE', 'SKYFLAT',
    'STANDARD', 'TRAILED', 'GUIDE', 'CATALOG',
)

PROPOSALS = (
    'calibrate', 'KEY2019AB-001', 'KEY2019AB-002', 'KEY2019AB-003',
    'DDT2019A-001', 'DDT2019B-003', 'LCOEPO2019A-004'
)


def frange(x, y, step):
    while x < y:
        yield x
        x += step


RA_RANGE = [round(i, 2) for i in frange(0.0, 360.0, 0.01)]
DEC_RANGE = [round(i, 2) for i in frange(-90.0, 90.0, 0.01)]


def get_header_list():
    directory = os.path.join(os.path.dirname(__file__))
    with open(os.path.join(directory, 'frames.json'), 'r') as frame_file:
        return json.load(frame_file)


class FuzzyBasename(factory.fuzzy.BaseFuzzyAttribute):
    def fuzz(self, *args, **kwargs):
        return '{site}{telescope_class}-{instrument}-{day_obs}-{frame_num}-{frame_type}'.format(
            site=random.choice(SITES).lower(),
            telescope_class=random.choice(['1m010', '1m020', '2m010', '0m410']),
            instrument=random.choice(INSTRUMENTS),
            day_obs=random.choice(['20190101', '20200101', '19911013', '19880717', '20200420', '20200124']),
            frame_num=str(random.choice(range(1, 10000))).zfill(4),
            frame_type=random.choice(EXTENSIONS)
        )


class FuzzyArea(factory.fuzzy.BaseFuzzyAttribute):
    def fuzz(self, as_dict=False):
        ra = random.choice(RA_RANGE)
        dec = random.choice(DEC_RANGE)
        # most of our frames will have a FOV less than 5deg
        x = random.choice(range(-5, 5))
        y = random.choice(range(-5, 5))
        se = (ra, dec)
        ne = (ra, dec + y)
        nw = (ra + x, dec + y)
        sw = (ra + x, dec)
        if as_dict:
            return {
                'type': 'Polygon',
                'coordinates': [[
                    [se[0], se[1]],
                    [ne[0], ne[1]],
                    [nw[0], nw[1]],
                    [sw[0], sw[1]],
                    [se[0], se[1]]
                ]]
            }

        return 'POLYGON(({0}, {1}, {2}, {3}, {4}))'.format(
            '{} {}'.format(se[0], se[1]),
            '{} {}'.format(ne[0], ne[1]),
            '{} {}'.format(nw[0], nw[1]),
            '{} {}'.format(sw[0], sw[1]),
            '{} {}'.format(se[0], se[1])
        )


class HeaderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Headers

    data = factory.fuzzy.FuzzyChoice(get_header_list().values())
    frame = factory.SubFactory('archive.frames.tests.factories.FrameFactory')


class VersionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Version

    created = factory.fuzzy.FuzzyDateTime(
        datetime.datetime(2015, 1, 1, tzinfo=UTC),
        datetime.datetime(2025, 1, 1, tzinfo=UTC)
    )
    key = factory.fuzzy.FuzzyText(length=32)
    md5 = factory.fuzzy.FuzzyText(length=32)
    extension = factory.fuzzy.FuzzyChoice(FORMATS)
    frame = factory.SubFactory('archive.frames.tests.factories.FrameFactory')


class FrameFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Frame

    basename = FuzzyBasename()
    area = FuzzyArea()
    DATE_OBS = factory.fuzzy.FuzzyDateTime(
        datetime.datetime(2015, 1, 1, tzinfo=UTC),
        timezone.now()
    )
    DAY_OBS = factory.fuzzy.FuzzyDate(
        datetime.date(2015, 1, 1),
        timezone.now().date()
    )
    PROPID = factory.fuzzy.FuzzyChoice(PROPOSALS)
    INSTRUME = factory.fuzzy.FuzzyChoice(INSTRUMENTS)
    OBJECT = factory.fuzzy.FuzzyText(length=10)
    SITEID = factory.fuzzy.FuzzyChoice(SITES)
    TELID = factory.fuzzy.FuzzyChoice(TELESCOPES)
    EXPTIME = factory.fuzzy.FuzzyFloat(0.0, 10000.0)
    FILTER = factory.fuzzy.FuzzyChoice(FILTERS)
    L1PUBDAT = factory.fuzzy.FuzzyDateTime(
        datetime.datetime(2015, 1, 1, tzinfo=UTC),
        datetime.datetime(2025, 1, 1, tzinfo=UTC)
    )
    OBSTYPE = factory.fuzzy.FuzzyChoice(OBSERVATION_TYPES)
    BLKUID = factory.fuzzy.FuzzyInteger(9000000)
    REQNUM = factory.fuzzy.FuzzyInteger(9000000)
    headers = factory.RelatedFactory(HeaderFactory, 'frame')

    @factory.post_generation
    def related_frames(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for frame in extracted:
                self.related_frames.add(frame)

    @factory.post_generation
    def version_set(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for version in extracted:
                self.version_set.add(version)
        else:
            version = VersionFactory(frame=self)
            self.version_set.add(version)


class PublicFrameFactory(FrameFactory):
    L1PUBDAT = datetime.datetime(2000, 1, 1, tzinfo=UTC)
