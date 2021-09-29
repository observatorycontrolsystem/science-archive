from archive.schema import ScienceArchiveSchema
from archive.frames.exceptions import FunpackError
from archive.frames.models import Frame, Version
from archive.frames.serializers import (
    AggregateSerializer, FrameSerializer, ZipSerializer, VersionSerializer, HeadersSerializer
)
from archive.frames.utils import (
    remove_dashes_from_keys, fits_keywords_only, build_nginx_zip_text, post_to_archived_queue,
    archived_queue_payload, get_s3_client
)
from archive.frames.permissions import AdminOrReadOnly
from archive.frames.filters import FrameFilter
from archive.doc_examples import EXAMPLE_RESPONSES
from rest_framework.decorators import action
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

logger = logging.getLogger()


class FrameViewSet(viewsets.ModelViewSet):
    permission_classes = (AdminOrReadOnly,)
    schema = ScienceArchiveSchema(tags=['Frames'])
    serializer_class = FrameSerializer
    filter_backends = (
        DjangoFilterBackend,
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
        if self.request.user.is_superuser:
            return queryset
        elif self.request.user.is_authenticated:
            return queryset.filter(
                Q(PROPID__in=self.request.user.profile.proposals) |
                Q(L1PUBDAT__lt=datetime.datetime.now(datetime.timezone.utc))
            )
        else:
            return queryset.filter(L1PUBDAT__lt=datetime.datetime.now(datetime.timezone.utc))

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

    @action(detail=True)
    def related(self, request, pk=None):
        """
        Return the related files associated with the archive record
        """
        frame = self.get_object()
        response_serializer = self.get_response_serializer(
            self.get_queryset().filter(pk__in=frame.related_frames.all()), many=True
        )
        return Response(response_serializer.data)

    @action(detail=True)
    def headers(self, request, pk=None):
        """
        Return the metadata (headers) associated with the archive record
        """
        frame = self.get_object()
        response_serializer = self.get_response_serializer(frame.headers)
        return Response(response_serializer.data)

    @xframe_options_exempt
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def zip(self, request):
        """
        Return a zip archive of files matching the frame IDs specified in the request
        """
        if request.data.get('auth_token'):  # Needed for hacky ajax file download nonsense
            token = get_object_or_404(Token, key=request.data['auth_token'])
            request.user = token.user
        request_serializer = self.get_request_serializer(data=request.data)
        if request_serializer.is_valid():
            frames = self.get_queryset().filter(pk__in=request_serializer.data['frame_ids'])
            if not frames.exists():
                return Response(status=status.HTTP_404_NOT_FOUND)
            filename = 'lcogtdata-{0}-{1}'.format(
                datetime.date.strftime(datetime.date.today(), '%Y%m%d'),
                frames.count()
            )
            body = build_nginx_zip_text(frames, filename, uncompress=request_serializer.data.get('uncompress'))
            response = HttpResponse(body, content_type='text/plain')
            response['X-Archive-Files'] = 'zip'
            response['Content-Disposition'] = 'attachment; filename={0}.zip'.format(filename)
            response['Set-Cookie'] = 'fileDownload=true; path=/'
            return response
        return Response(request_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    def _get_aggregate_values(query_set, field, aggregate_field):
        if aggregate_field in ('ALL', field):
            return [i[0] for i in query_set.values_list(field).distinct() if i[0]]
        else:
            return []

    @action(detail=False)
    def aggregate(self, request):
        """
        Aggregate field values based on start/end time
        """
        fields = ('SITEID', 'TELID', 'FILTER', 'INSTRUME', 'OBSTYPE', 'PROPID')
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
            query_filters['DATE_OBS__gte'] = parse(request.GET['start']).replace(tzinfo=UTC, second=0, microsecond=0)
        if 'end' in request.GET:
            query_filters['DATE_OBS__lte'] = parse(request.GET['end']).replace(tzinfo=UTC, second=0, microsecond=0)
        cache_hash = blake2s(repr(frozenset(list(query_filters.items()) + [aggregate_field])).encode()).hexdigest()
        response_dict = cache.get(cache_hash)
        if not response_dict:
            qs = Frame.objects.order_by().filter(**query_filters)
            sites = self._get_aggregate_values(qs, 'SITEID', aggregate_field)
            telescopes = self._get_aggregate_values(qs, 'TELID', aggregate_field)
            filters = self._get_aggregate_values(qs, 'FILTER', aggregate_field)
            instruments = self._get_aggregate_values(qs, 'INSTRUME', aggregate_field)
            obstypes = self._get_aggregate_values(qs, 'OBSTYPE', aggregate_field)
            proposals = self._get_aggregate_values(qs.filter(L1PUBDAT__lte=timezone.now()), 'PROPID', aggregate_field)
            response_dict = {
                'sites': sites,
                'telescopes': telescopes,
                'filters': filters,
                'instruments': instruments,
                'obstypes': obstypes,
                'proposals': proposals
            }
            cache.set(cache_hash, response_dict, 60 * 60)
        response_serializer = self.get_response_serializer(response_dict)
        return Response(response_serializer.data)

    def get_request_serializer(self, *args, **kwargs):
        request_serializers = {'zip': ZipSerializer}
        
        return request_serializers.get(self.action, self.serializer_class)(*args, **kwargs)

    def get_response_serializer(self, *args, **kwargs):
        response_serializers = {'aggregate':  AggregateSerializer,
                                'headers': HeadersSerializer,
                                'related': FrameSerializer}
        
        return response_serializers.get(self.action, self.serializer_class)(*args, **kwargs)

    def get_example_response(self):
        example_responses = {'zip': Response(EXAMPLE_RESPONSES['frames']['zip'], 200, content_type='application/zip'),
                             'headers': Response(EXAMPLE_RESPONSES['frames']['headers'], 200)}

        return example_responses.get(self.action)

    def get_endpoint_name(self):
        endpoint_names = {'aggregate': 'aggregateFields',
                          'headers': 'getHeaders',
                          'related': 'getRelatedFrames',
                          'zip': 'getZipArchive'}

        return endpoint_names.get(self.action)

class VersionViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (IsAdminUser,)
    serializer_class = VersionSerializer
    schema = ScienceArchiveSchema(tags=['Versions'])
    # Always use the default (writer) database instead of the reader to get the most up-to-date
    # data, as the available endpoint on this admin viewset is used to check whether a version
    # already exists before attempting to ingest a new version.
    queryset = Version.objects.using('default').all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('md5',)


class S3ViewSet(viewsets.ViewSet):
    schema = ScienceArchiveSchema(tags=['Frames'])

    @action(detail=True)
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
        client = get_s3_client()

        with io.BytesIO() as fileobj:
            # download from AWS S3 into an in-memory object
            client.download_fileobj(Bucket=version.data_params['Bucket'],
                                    Key=version.data_params['Key'],
                                    Fileobj=fileobj)
            fileobj.seek(0)

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
    
    def get_example_response(self):
        example_responses = {'funpack': Response(EXAMPLE_RESPONSES['frames']['funpack'], 
                                                 status=status.HTTP_200_OK, content_type='application/octet-stream')}

        return example_responses.get(self.action)

    def get_endpoint_name(self):
        endpoint_names = {'funpack': 'getFunpackedFile'}

        return endpoint_names.get(self.action)
