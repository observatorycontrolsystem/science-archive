from archive.frames.exceptions import FunpackError
from archive.frames.models import Frame, Version
from archive.frames.serializers import (
    FrameSerializer, ZipSerializer, VersionSerializer, HeadersSerializer
)
from archive.frames.utils import (
    build_nginx_zip_text, post_to_archived_queue,
    archived_queue_payload, get_file_store_path
)
from archive.frames.permissions import AdminOrReadOnly
from archive.frames.filters import FrameFilter

from rest_framework.decorators import list_route, detail_route
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework import status, filters, viewsets
from rest_framework.authtoken.models import Token
from django_filters.rest_framework import DjangoFilterBackend
from django.http import HttpResponse
from django.db.models import Q, Prefetch
from django.views.decorators.clickjacking import xframe_options_exempt
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from dateutil.parser import parse
from django.utils import timezone
from hashlib import blake2s
from pytz import UTC
import subprocess
import datetime
import logging
import io

from ocs_archive.storage.filestore import FileStore
from ocs_archive.storage.filestorefactory import FileStoreFactory
from ocs_archive.settings import settings as archive_settings

logger = logging.getLogger()


class FrameViewSet(viewsets.ModelViewSet):
    permission_classes = (AdminOrReadOnly,)
    serializer_class = FrameSerializer
    filter_backends = (
        DjangoFilterBackend,
        filters.OrderingFilter,
    )
    filter_class = FrameFilter
    ordering_fields = ('id', 'basename', 'observation_date', 'primary_filter', 'configuration_type',
                       'proposal_id', 'instrument_id', 'target_name', 'reduction_level', 'exposure_time')

    def get_queryset(self):
        """
        Filter frames depending on the logged in user.
        Admin users see all frames, excluding ones which have no versions.
        Authenticated users see all frames with a PUBDAT in the past, plus
        all frames that belong to their proposals.
        Non authenticated see all frames with a PUBDAT in the past
        """
        queryset = (
            Frame.objects.exclude(observation_date=None)
            .prefetch_related('version_set')
            .prefetch_related(Prefetch('related_frames', queryset=Frame.objects.all().only('id')))
        )
        if self.request.user.is_superuser:
            return queryset
        elif self.request.user.is_authenticated:
            return queryset.filter(
                Q(proposal_id__in=self.request.user.profile.proposals) |
                Q(oublic_date__lt=datetime.datetime.now(datetime.timezone.utc))
            )
        else:
            return queryset.filter(public_date__lt=datetime.datetime.now(datetime.timezone.utc))

    def create(self, request):
        basename = request.data.get('basename')
        if len(request.data.get('version_set')) > 0:
            extension = request.data.get('version_set')[0].get('extension')
        else:
            extension = ''
        logger_tags = {'tags': {
            'filename': '{}{}'.format(basename, extension),
            'request_id': request.data.get('request_id')
        }}
        logger.info('Got request to process frame', extra=logger_tags)

        frame_serializer = FrameSerializer(data=request.data)
        if frame_serializer.is_valid():
            frame = frame_serializer.save()
            logger_tags['tags']['id'] = frame.id
            logger.info('Created frame', extra=logger_tags)
            try:
                post_to_archived_queue(archived_queue_payload(dictionary=request.data, frame=frame))
            except Exception:
                logger.exception('Failed to post frame to archived queue', extra=logger_tags)
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
            body = build_nginx_zip_text(frames, filename, uncompress=serializer.data.get('uncompress'))
            response = HttpResponse(body, content_type='text/plain')
            response['X-Archive-Files'] = 'zip'
            response['Content-Disposition'] = 'attachment; filename={0}.zip'.format(filename)
            response['Set-Cookie'] = 'fileDownload=true; path=/'
            return response
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    def _get_aggregate_values(query_set, field, aggregate_field):
        if aggregate_field in ('ALL', field):
            return [i[0] for i in query_set.values_list(field).distinct() if i[0]]
        else:
            return []

    @list_route()
    def aggregate(self, request):
        fields = ('site_id', 'telescope_id', 'primary_filter', 'instrument_id', 'configuration_type', 'proposal_id')
        aggregate_field = request.GET.get('aggregate_field', 'ALL')
        if aggregate_field != 'ALL' and aggregate_field not in fields:
            return Response(
                'Invalid aggregate_field. Valid fields are {}'.format(', '.join(fields)),
                status=status.HTTP_400_BAD_REQUEST
            )
        query_filters = {}
        for k in fields:
            if request.GET.get(k):
                query_filters[k] = request.GET[k]
        if 'start' in request.GET:
            query_filters['observation_date__gte'] = parse(request.GET['start']).replace(tzinfo=UTC, second=0, microsecond=0)
        if 'end' in request.GET:
            query_filters['observation_date__lte'] = parse(request.GET['end']).replace(tzinfo=UTC, second=0, microsecond=0)
        cache_hash = blake2s(repr(frozenset(list(query_filters.items()) + [aggregate_field])).encode()).hexdigest()
        response_dict = cache.get(cache_hash)
        if not response_dict:
            qs = Frame.objects.order_by().filter(**query_filters)
            sites = self._get_aggregate_values(qs, 'site_id', aggregate_field)
            telescopes = self._get_aggregate_values(qs, 'telescope_id', aggregate_field)
            filters = self._get_aggregate_values(qs, 'primary_filter', aggregate_field)
            instruments = self._get_aggregate_values(qs, 'instrument_id', aggregate_field)
            obstypes = self._get_aggregate_values(qs, 'configuration_type', aggregate_field)
            proposals = self._get_aggregate_values(qs.filter(public_date__lte=timezone.now()), 'proposal_id', aggregate_field)
            response_dict = {
                'sites': sites,
                'telescopes': telescopes,
                'filters': filters,
                'instruments': instruments,
                'obstypes': obstypes,
                'proposals': proposals
            }
            cache.set(cache_hash, response_dict, 60 * 60)
        return Response(response_dict)


class VersionViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (IsAdminUser,)
    serializer_class = VersionSerializer
    # Always use the default (writer) database instead of the reader to get the most up-to-date
    # data, as the available endpoint on this admin viewset is used to check whether a version
    # already exists before attempting to ingest a new version.
    queryset = Version.objects.using('default').all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('md5',)


class S3ViewSet(viewsets.ViewSet):

    @detail_route()
    def funpack(self, request, pk=None):
        '''
        Download the given Version (one part of a Frame), run funpack on it, and
        return the uncompressed FITS file to the client.

        This is designed to be used by the Archive Client ZIP file support to
        automatically uncompress FITS files for clients that cannot do it
        themselves.
        '''

        logger.info(msg='Downloading file via funpack endpoint')

        version = get_object_or_404(Version, pk=pk)
        file_store = FileStoreFactory.get_file_store_class()()
        path = get_file_store_path(version.frame.filename, version.frame.get_header_dict())

        with file_store.get_fileobj(path) as fileobj:
            # FITS unpack
            cmd = ['/usr/bin/funpack', '-C', '-S', '-', ]
            try:
                proc = subprocess.run(cmd, input=fileobj.getvalue(), stdout=subprocess.PIPE)
                proc.check_returncode()
            except subprocess.CalledProcessError as cpe:
                logger.error(f'funpack failed with return code {cpe.returncode} and error {cpe.stderr}')
                raise FunpackError

            # return it to the client
            return HttpResponse(bytes(proc.stdout), content_type='application/octet-stream')
