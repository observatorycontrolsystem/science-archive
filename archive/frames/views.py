from archive.frames.models import Frame
from archive.frames.serializers import FrameSerializer, ZipSerializer
from archive.frames.utils import remove_dashes_from_keys, fits_keywords_only, build_nginx_zip_text
from archive.frames.permissions import AdminOrReadOnly
from archive.frames.filters import FrameFilter
from rest_framework.decorators import list_route
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status, filters, viewsets
from django.http import HttpResponse
from django.db.models import Q, Prefetch
from opentsdb_python_metrics.metric_wrappers import send_tsdb_metric
import logging
import datetime

logger = logging.getLogger()


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
    permission_classes = (AdminOrReadOnly,)
    serializer_class = FrameSerializer
    filter_backends = (
        filters.DjangoFilterBackend,
        filters.OrderingFilter,
    )
    filter_class = FrameFilter
    ordering_fields = ('id', 'filename', 'DATE_OBS',
                       'PROPID', 'INSTRUME', 'OBJECT', 'RLEVEL')

    def get_queryset(self):
        """
        Filter frames depending on the logged in user.
        Admin users see all frames, excluding ones which have no versions.
        Authenticated users see all frames with a PUBDAT in the past, plus
        all frames that belong to their proposals.
        Non authenticated see all frames with a PUBDAT in the past
        """
        queryset = (
            Frame.objects.exclude(version=None)
            .prefetch_related('version_set')
            .prefetch_related(Prefetch('related_frames', queryset=Frame.objects.all().only('id')))
        )
        if self.request.user.is_staff:
            return queryset
        elif self.request.user.is_authenticated():
            return queryset.filter(
                Q(PROPID__in=self.request.user.profile.proposals) |
                Q(L1PUBDAT__lt=datetime.datetime.utcnow()) |
                Q(L1PUBDAT=None)
            )
        else:
            return queryset.filter(
                Q(L1PUBDAT__lt=datetime.datetime.utcnow()) |
                Q(L1PUBDAT=None)
            )

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

    @list_route(methods=['post'], permission_classes=[AllowAny])
    def zip(self, request):
        serializer = ZipSerializer(data=request.data)
        if serializer.is_valid():
            frames = self.get_queryset().filter(pk__in=serializer.data['frame_ids'])
            body = build_nginx_zip_text(frames)
            response = HttpResponse(body, content_type='text/plain')
            response['X-Archive-Files'] = 'zip'
            response['Content-Disposition'] = 'attachment; filename=lcogtdata.zip'
            return response
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
