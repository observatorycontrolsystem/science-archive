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


logger = logging.getLogger()


class FrameFilter(django_filters.FilterSet):
    start = django_filters.DateTimeFilter(name='DATE_OBS', lookup_type='gte')
    end = django_filters.DateTimeFilter(name='DATE_OBS', lookup_type='lte')
    area = django_filters.CharFilter(lookup_type='contains')

    class Meta:
        model = Frame
        fields = ['filename', 'DATE_OBS', 'USERID', 'PROPID',
                  'INSTRUME', 'OBJECT', 'start', 'end', 'area']


class FrameViewSet(viewsets.ModelViewSet):
    queryset = Frame.objects.exclude(version=None).prefetch_related('version_set')
    serializer_class = FrameSerializer
    filter_backends = (
        filters.DjangoFilterBackend,
        filters.OrderingFilter,
    )
    filter_class = FrameFilter
    ordering_fields = ('id', 'filename', 'DATE_OBS', 'USERID',
                       'PROPID', 'INSTRUME', 'OBJECT')

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
