from archive.frames.models import Frame
from archive.frames.serializers import FrameSerializer
from archive.frames.utils import remove_dashes_from_keys, fits_keywords_only
from rest_framework.response import Response
from rest_framework import status
from rest_framework import filters
from rest_framework import viewsets
import logging
import django_filters
from opentsdb_python_metrics.metric_wrappers import send_tsdb_metric
from rest_framework_gis.filterset import GeoFilterSet
from rest_framework_gis import filters as geofilters


logger = logging.getLogger()


class FrameFilter(GeoFilterSet):
    start = django_filters.DateTimeFilter(name='DATE_OBS', lookup_type='gte')
    end = django_filters.DateTimeFilter(name='DATE_OBS', lookup_type='lte')
    covers = geofilters.GeometryFilter(name='area', lookup_type='covers')

    class Meta:
        model = Frame
        fields = ['filename', 'DATE_OBS', 'USERID', 'PROPID',
                  'INSTRUME', 'OBJECT', 'start', 'end', 'area',
                  'RLEVEL']


class FrameViewSet(viewsets.ModelViewSet):
    """
    `/frames/` Returns a list of frames.

    `/frames/<id>/` Returns a single frame.

    The `/frames/` resource accepts several query paramters that can be
    used to filter the returned results. These parameters are: `filename`,
    `DATE-OBS`, `USERID`, `PROPID`, `INSTRUME`, `OBJECT`, `start`, `end`, `area`.

    `start` and `end` accept dates from which to return data (via `DATE-OBS`). Ex:
    `?start=2016-10-24&end=2016-10-25`

    `area` accepts a ra, dec pair in the form of (RA,DEC). Ex:
    `?area=(55.24,-8.4)`

    All other fields use equality based filtering. Ex:
    `?USERID=austin.riba&OBJECT=M42`
    """
    queryset = Frame.objects.exclude(version=None).prefetch_related('version_set')
    serializer_class = FrameSerializer
    filter_backends = (
        filters.DjangoFilterBackend,
        filters.OrderingFilter,
    )
    filter_class = FrameFilter
    ordering_fields = ('id', 'filename', 'DATE_OBS', 'USERID',
                       'PROPID', 'INSTRUME', 'OBJECT', 'RLEVEL')

    def create(self, request):
        send_tsdb_metric('archive.frame_posted', 1)
        filename = request.data.get('filename')
        logger_tags = {'tags': {'filename': filename}}
        logger.info('Got request to process frame', extra=logger_tags)
        data = remove_dashes_from_keys(request.data)
        frame_serializer = FrameSerializer(data=data)
        if frame_serializer.is_valid():
            frame_serializer.save(header=fits_keywords_only(data))
            logger.info('Request to process frame succeeded', extra=logger_tags)
            return Response(frame_serializer.data, status=status.HTTP_201_CREATED)
        else:
            logger_tags['tags']['errors'] = frame_serializer.errors
            logger.fatal('Request to process frame failed', extra=logger_tags)
            return Response(frame_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
