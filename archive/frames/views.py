from archive.frames.models import Frame, Version
from archive.frames.serializers import (
    FrameSerializer, ZipSerializer, VersionSerializer, HeadersSerializer
)
from archive.frames.utils import remove_dashes_from_keys, fits_keywords_only, build_nginx_zip_text
from archive.frames.permissions import AdminOrReadOnly
from archive.frames.filters import FrameFilter
from rest_framework.decorators import list_route, detail_route
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework import status, filters, viewsets
from rest_framework.authtoken.models import Token
from django.http import HttpResponse
from django.db.models import Q, Prefetch
from django.views.decorators.clickjacking import xframe_options_exempt
from django.shortcuts import get_object_or_404
from django.core.cache import cache
import logging
import datetime

logger = logging.getLogger()


class FrameViewSet(viewsets.ModelViewSet):
    permission_classes = (AdminOrReadOnly,)
    serializer_class = FrameSerializer
    filter_backends = (
        filters.DjangoFilterBackend,
        filters.OrderingFilter,
    )
    filter_class = FrameFilter
    ordering_fields = ('id', 'basename', 'DATE_OBS', 'FILTER', 'OBSTYPE',
                       'PROPID', 'INSTRUME', 'OBJECT', 'RLEVEL', 'EXPTIME')

    def get_queryset(self):
        """
        Filter frames depending on the logged in user.
        Admin users see all frames, excluding ones which have no versions.
        Authenticated users see all frames with a PUBDAT in the past, plus
        all frames that belong to their proposals.
        Non authenticated see all frames with a PUBDAT in the past
        """
        queryset = (
            Frame.objects.exclude(DATE_OBS=None)
            .prefetch_related('version_set')
            .prefetch_related(Prefetch('related_frames', queryset=Frame.objects.all().only('id')))
        )
        if self.request.user.is_staff:
            return queryset
        elif self.request.user.is_authenticated():
            return queryset.filter(
                Q(PROPID__in=self.request.user.profile.proposals) |
                Q(L1PUBDAT__lt=datetime.datetime.utcnow())
            )
        else:
            return queryset.filter(L1PUBDAT__lt=datetime.datetime.utcnow())

    def create(self, request):
        basename = request.data.get('basename')
        if len(request.data.get('version_set')) > 0:
            extension = request.data.get('version_set')[0].get('extension')
        else:
            extension = ''
        logger_tags = {'tags': {
            'filename': '{}{}'.format(basename, extension),
            'request_num': request.data.get('REQNUM')
        }}
        logger.info('Got request to process frame', extra=logger_tags)

        data = remove_dashes_from_keys(request.data)
        frame_serializer = FrameSerializer(data=data)
        if frame_serializer.is_valid():
            frame = frame_serializer.save(header=fits_keywords_only(data))
            logger_tags['tags']['id'] = frame.id
            logger.info('Request to process frame succeeded', extra=logger_tags)
            return Response(frame_serializer.data, status=status.HTTP_201_CREATED)
        else:
            logger_tags['tags']['errors'] = frame_serializer.errors
            logger.fatal('Request to process frame failed', extra=logger_tags)
            return Response(frame_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @detail_route()
    def related(self, request, pk=None):
        frame = self.get_object()
        serializer = self.get_serializer(
            self.get_queryset().filter(pk__in=frame.related_frames.all()), many=True
        )
        return Response(serializer.data)

    @detail_route()
    def headers(self, request, pk=None):
        frame = self.get_object()
        serializer = HeadersSerializer(frame.headers)
        return Response(serializer.data)

    @xframe_options_exempt
    @list_route(methods=['post'], permission_classes=[AllowAny])
    def zip(self, request):
        if request.data.get('auth_token'):  # Needed for hacky ajax file download nonsense
            token = get_object_or_404(Token, key=request.data['auth_token'])
            request.user = token.user
        serializer = ZipSerializer(data=request.data)
        if serializer.is_valid():
            frames = self.get_queryset().filter(pk__in=serializer.data['frame_ids'])
            if not frames.exists():
                return Response(status=status.HTTP_404_NOT_FOUND)
            filename = 'lcogtdata-{0}-{1}'.format(
                datetime.date.strftime(datetime.date.today(), '%Y%m%d'),
                frames.count()
            )
            body = build_nginx_zip_text(frames, filename)
            response = HttpResponse(body, content_type='text/plain')
            response['X-Archive-Files'] = 'zip'
            response['Content-Disposition'] = 'attachment; filename={0}.zip'.format(filename)
            response['Set-Cookie'] = 'fileDownload=true; path=/'
            return response
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @list_route()
    def aggregate(self, request):
        response_dict = cache.get('aggregate')
        if not response_dict:
            sites = [i[0] for i in Frame.objects.order_by().values_list('SITEID').distinct() if i[0]]
            telescopes = [i[0] for i in Frame.objects.order_by().values_list('TELID').distinct() if i[0]]
            filters = [i[0] for i in Frame.objects.order_by().values_list('FILTER').distinct()if i[0]]
            instruments = [i[0] for i in Frame.objects.order_by().values_list('INSTRUME').distinct() if i[0]]
            obstypes = [i[0] for i in Frame.objects.order_by().values_list('OBSTYPE').distinct() if i[0]]
            proposals = [
                i[0] for i in Frame.objects.filter(L1PUBDAT__lte=datetime.datetime.utcnow())
                                           .order_by().values_list('PROPID')
                                           .distinct() if i[0]
            ]
            response_dict = {
                'sites': sites,
                'telescopes': telescopes,
                'filters': filters,
                'instruments': instruments,
                'obstypes': obstypes,
                'proposals': proposals
            }
            cache.set('aggregate', response_dict, 60 * 60)
        return Response(response_dict)


class VersionViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (IsAdminUser,)
    serializer_class = VersionSerializer
    queryset = Version.objects.all()
    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('md5',)
