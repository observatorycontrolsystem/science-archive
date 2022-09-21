from archive.schema import ScienceArchiveSchema
from archive.frames.exceptions import FunpackError
from archive.frames.models import Frame, Version
from archive.frames.serializers import (
    AggregateSerializer, FrameSerializer, ZipSerializer, VersionSerializer, HeadersSerializer
)
from archive.frames.utils import (
    build_nginx_zip_text, post_to_archived_queue,
    archived_queue_payload, get_file_store_path
)
from archive.frames.permissions import AdminOrReadOnly
from archive.frames.filters import FrameFilter

from archive.doc_examples import EXAMPLE_RESPONSES, QUERY_PARAMETERS
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
from django.conf import settings
from pytz import UTC
from django.db import connections, OperationalError
from django.db.models.functions import Now
from django.utils.cache import patch_response_headers
from hashlib import blake2b

import subprocess
import datetime
import logging

from ocs_archive.storage.filestorefactory import FileStoreFactory
from ocs_authentication.auth_profile.models import AuthProfile

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
    ordering_fields = ('id', 'basename', 'observation_date', 'primary_optical_element', 'configuration_type',
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
                Q(public_date__lt=datetime.datetime.now(datetime.timezone.utc))
            )
        else:
            return queryset.filter(public_date__lt=datetime.datetime.now(datetime.timezone.utc))

    # These two method overrides just force the use of the as_dict method for serialization for list and detail endpoints
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        json_models = [model.as_dict() for model in page]
        return self.get_paginated_response(json_models)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        return Response(instance.as_dict())

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
            # Need to try the AuthProfile token first, and then the auth token, and if neither exists then return 403
            try:
                token = AuthProfile.objects.get(api_token=request.data['auth_token'])
            except AuthProfile.DoesNotExist:
                token = get_object_or_404(Token, key=request.data['auth_token'])
            request.user = token.user
        request_serializer = self.get_request_serializer(data=request.data)
        if request_serializer.is_valid():
            frames = self.get_queryset().filter(pk__in=request_serializer.data['frame_ids'])
            if not frames.exists():
                return Response(status=status.HTTP_404_NOT_FOUND)
            filename = '{0}-{1}-{2}'.format(
                settings.ZIP_DOWNLOAD_FILENAME_BASE,
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


    @action(detail=False)
    def aggregate(self, request):
        """
        Aggregate field values based on start/end time.
        Returns the unique values shared across all FITS files for site, telescope, instrument, filter, proposal, and obstype.

        Aggregation with filters is done on a best effort basis. If it takes too long, the filters are effectively ignored,
        returning a (most likely cached) response of all distict values.
        """
        start = request.query_params.get("start")
        end = request.query_params.get("end")
        public = request.query_params.get("public", False)
        site_id = request.query_params.get("site_id")
        telescope_id = request.query_params.get("telescope_id")
        primary_optical_element = request.query_params.get("primary_optical_element")
        instrument_id = request.query_params.get("instrument_id")
        configuration_type = request.query_params.get("configuration_type")
        proposal_id = request.query_params.get("proposal_id")

        if start:
            start = parse(start).replace(tzinfo=UTC, second=0, microsecond=0)

        if end:
            end = parse(end).replace(tzinfo=UTC, second=0, microsecond=0)

        cache_key_elms = [
            start,
            end,
            public,
            site_id,
            telescope_id,
            primary_optical_element,
            instrument_id,
            configuration_type,
            proposal_id,
        ]

        # unauthenticated users share the cache space
        # authenticated users each get their own cache
        if request.user.is_authenticated:
            cache_key_elms.append(request.user.id)

        cache_key = blake2b("|".join(map(str, cache_key_elms)).encode("utf-8")).hexdigest()

        response_dict = cache.get(cache_key)

        if response_dict:
            response_serializer = self.get_response_serializer(response_dict)
            return Response(response_serializer.data)

        frames = Frame.objects.all()

        if start:
            frames = frames.filter(observation_date__gte=start)

        if end:
            frames = frames.filter(observation_date__lt=end)

        if not public:
            logger.info("excluding public data")
            frames = frames.exclude(public_date__lt=Now())

        if site_id:
            frames = frames.filter(site_id=site_id)

        if telescope_id:
            frames = frames.filter(telescope_id=telescope_id)

        if primary_optical_element:
            frames = frames.filter(primary_optical_element=primary_optical_element)

        if instrument_id:
            frames = frames.filter(instrument_id=instrument_id)

        if configuration_type:
            frames = frames.filter(configuration_type=configuration_type)

        if proposal_id:
            frames = frames.filter(proposal_id=proposal_id)

        # Limit non-authenticated users to only public data always to avoid
        # leaking stuff. Probably don't have sensitive info in the aggregates,
        # but why not. It'll at least help with limiting the query scan.
        if not request.user.is_authenticated:
            logger.info("limiting unauthenticated user to only public data")
            frames = frames.exclude(public_date__gte=Now())
        elif not request.user.is_superuser:
            user_proposals = request.user.profile.proposals or []

            # Authenticated users can only view their non-public data
            if user_proposals:
                logger.info("limiting authenticated user to only their data")
                frames = frames.filter(
                    public_date__gte=Now(),
                    proposal_id__in=user_proposals
                )
            else:
                logger.info("no proposals found for user; limiting to public only")
                frames = frames.exclude(public_date__gte=Now())

        try:
            # If a superuser is making this request, don't limit the query time.
            # Also means they won't hit the cache.
            if request.user.is_authenticated and request.user.is_superuser:
                timeout = 0
            else:
                timeout = 500
            response_dict = self._agg_sql(frames, timeout)
        except OperationalError:
            logger.info("filtered aggregation timed out")

            # If we timeout, return a long-lived cached copy of every single
            # possible value for every publicly visible field.
            all_cache_key = "all_public_aggregates"
            response_dict = cache.get(all_cache_key)
            if not response_dict:
                frames = Frame.objects.all().exclude(public_date__gte=Now())
                response_dict = self._agg_sql(frames, 0)

                # cache for an hour
                cache.set(all_cache_key, response_dict, 60 * 60)

        # cache the specific response 30 secs
        cache.set(cache_key, response_dict, 30)

        response_serializer = self.get_response_serializer(response_dict)
        response =  Response(response_serializer.data)
        patch_response_headers(response, 30)

        return response

    def _agg_sql(self, frames, timeout=0):
        frames = frames.values_list(
            "proposal_id",
            "site_id",
            "telescope_id",
            "instrument_id",
            "configuration_type",
            "primary_optical_element",
        ).distinct().order_by()

        with connections["replica"].cursor() as cursor:
            distinct_sql, params = frames.query.sql_with_params()
            query_sql = f"""
              SET LOCAL statement_timeout TO {timeout};
              SELECT
                array_agg(DISTINCT site_id) FILTER (WHERE site_id <> ''),
                array_agg(DISTINCT telescope_id) FILTER (WHERE telescope_id <> ''),
                array_agg(DISTINCT primary_optical_element) FILTER (WHERE primary_optical_element <> ''),
                array_agg(DISTINCT instrument_id) FILTER (WHERE instrument_id <> ''),
                array_agg(DISTINCT configuration_type) FILTER (WHERE configuration_type <> ''),
                array_agg(DISTINCT proposal_id) FILTER (WHERE proposal_id <> '')
              FROM ({distinct_sql}) as t;
            """
            logger.info("executing aggregate query: %s", query_sql)
            cursor.execute(query_sql, params)
            row = cursor.fetchone()

        response_dict = dict(
          sites=row[0] or [],
          telescopes=row[1] or [],
          filters=row[2] or [],
          instruments=row[3] or [],
          obstypes=row[4] or [],
          proposals=row[5] or [],
        )

        return response_dict


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

    def get_query_parameters(self):
        query_parameters = {'aggregate': QUERY_PARAMETERS['frames']['aggregate']}

        return query_parameters.get(self.action)

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


class FunpackViewSet(viewsets.ViewSet):
    schema = ScienceArchiveSchema(tags=['Frames'])

    @action(detail=True)
    def funpack(self, request, pk=None):
        '''
        Instruct the server to download the given Version (one part of a Frame), run funpack on it, and
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

    def get_example_response(self):
        example_responses = {'funpack': Response(EXAMPLE_RESPONSES['frames']['funpack'],
                                                 status=status.HTTP_200_OK, content_type='application/octet-stream')}

        return example_responses.get(self.action)

    def get_endpoint_name(self):
        endpoint_names = {'funpack': 'getFunpackedFile'}

        return endpoint_names.get(self.action)
