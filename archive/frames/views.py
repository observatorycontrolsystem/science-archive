from archive.schema import ScienceArchiveSchema
from archive.frames.exceptions import FunpackError
from archive.frames.models import Frame, Version
from archive.frames.serializers import (
    AggregateSerializer, FrameSerializer, ZipSerializer, VersionSerializer,
    HeadersSerializer, AggregateQueryParamsSeralizer,
)
from archive.frames.utils import (
    build_nginx_zip_text, post_to_archived_queue,
    archived_queue_payload, get_file_store_path,
    aggregate_frames_sql, get_cached_frames_aggregates

)
from archive.frames.permissions import AdminOrReadOnly
from archive.frames.filters import FrameFilter

from archive.doc_examples import EXAMPLE_RESPONSES, QUERY_PARAMETERS
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework import status, filters, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import APIException
from django_filters.rest_framework import DjangoFilterBackend
from django.http import HttpResponse
from django.db.models import Q, Prefetch
from django.views.decorators.clickjacking import xframe_options_exempt
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.conf import settings
from pytz import UTC
from django.db import OperationalError
from django.db.models.functions import Now
from django.utils.cache import patch_response_headers
from django.views.decorators.vary import vary_on_headers
from astropy.io import fits
from hashlib import blake2b

import subprocess
import datetime
import logging
import io

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
            body = build_nginx_zip_text(frames, filename, uncompress=request_serializer.data.get('uncompress'), 
                                        catalog_only=request_serializer.data.get('catalog_only'))
            response = HttpResponse(body, content_type='text/plain')
            response['X-Archive-Files'] = 'zip'
            response['Content-Disposition'] = 'attachment; filename={0}.zip'.format(filename)
            response['Set-Cookie'] = 'fileDownload=true; path=/'
            return response
        return Response(request_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    @vary_on_headers("Cookie", "Authorization")
    @action(detail=False)
    def aggregate(self, request):
        """
        Aggregate field values based on start/end time.
        Returns the unique values shared across all FITS files for site, telescope, instrument, filter, proposal, and obstype.

        Requests without a time range are returned from a pre-computed cache
        populated by the management command: `python manage.py cacheaggregates`.

        If a start/end time is specified, it must be less than 365 days.
        """
        qp = AggregateQueryParamsSeralizer(data=request.query_params)
        qp.is_valid(raise_exception=True)
        query_params = qp.validated_data

        start = query_params.get("start")
        end = query_params.get("end")
        include_public = query_params.get("public")
        site_id = query_params.get("site_id")
        telescope_id = query_params.get("telescope_id")
        primary_optical_element = query_params.get("primary_optical_element")
        instrument_id = query_params.get("instrument_id")
        configuration_type = query_params.get("configuration_type")
        proposal_id = query_params.get("proposal_id")

        # allow setting SQL query timeout
        # between 0 & 20s; default is 2s; 0 = inf
        query_timeout = query_params.get("query_timeout")

        is_authenticated = request.user.is_authenticated
        is_superuser = request.user.is_superuser

        # 24 hours
        # aggregates for public frames (public_date < now()) are shared by
        # both authenticated & unauthenticated users and not very likely to
        # change so we can get away with a long timeout.
        public_cache_timeout = 24 * 60 * 60

        # 5 min
        # Every authenticated user has their own cache of aggregates over
        # the proposals they are part of (frame.proposal_id IN user_proposals)
        # So, don't expect a lot of hits, but might be good if they're going
        # back and forth in short bursts of activity.
        private_cache_timeout = 5 * 60

        if not is_authenticated:
            # limit unauthenticated users to a smaller query timeout (500 ms)
            query_timeout = min(query_timeout, 1000)


        if all(
            x is None for x in [
              start, end, include_public, site_id, telescope_id, primary_optical_element,
              instrument_id, configuration_type, proposal_id
            ]
        ):
            return self._agg_frames_all_resp()

        if start is None or end is None:
            return Response(
                "both start & end must be specified",
                status=status.HTTP_400_BAD_REQUEST
            )

        start = start.replace(tzinfo=UTC, second=0, microsecond=0)
        end = end.replace(tzinfo=UTC, second=0, microsecond=0)

        if (end - start) > datetime.timedelta(days=365):
            return Response(
                "time range must be less than or equal to a year (365 days)",
                status=status.HTTP_400_BAD_REQUEST
            )

        # Expire the public cache quicker if the query window is in the future
        # to avoid serving stale public aggregates for too long.
        if end >= datetime.datetime.now(tz=UTC):
            # 1 hour
            public_cache_timeout = 60 * 60

        frames = Frame.objects.all()

        frames = frames.filter(observation_date__gte=start)

        frames = frames.filter(observation_date__lt=end)

        if proposal_id is not None:
            frames = frames.filter(proposal_id=proposal_id)

        if configuration_type is not None:
            frames = frames.filter(configuration_type=configuration_type)

        if site_id is not None:
            frames = frames.filter(site_id=site_id)

        if telescope_id is not None:
            frames = frames.filter(telescope_id=telescope_id)

        if instrument_id is not None:
            frames = frames.filter(instrument_id=instrument_id)

        if primary_optical_element is not None:
            frames = frames.filter(primary_optical_element=primary_optical_element)

        cache_key_elms = [
            settings.SECRET_KEY,
            start,
            end,
            proposal_id,
            configuration_type,
            site_id,
            telescope_id,
            instrument_id,
            primary_optical_element,
        ]

        if include_public:
            public_cache_key = "agg_public_%s" % blake2b(
                "|".join(
                  map(str, cache_key_elms)
                ).encode("utf-8")
            ).hexdigest()

            public_agg = cache.get(public_cache_key)

            if public_agg is None:
                logger.info("public agg cache miss")
                public_frames = frames.all().filter(public_date__lte=Now())
                public_agg = self._agg_frames_sql(public_frames, query_timeout)
                cache.set(public_cache_key, public_agg, public_cache_timeout)
            else:
                logger.info("public agg cache hit")
        else:
            # doesn't actually do a query
            public_agg = self._agg_frames_sql(frames.none(), public_cache_timeout)

        # Exit early: unauthenticated users have no non-public data to view
        # No point in making DB calls to return nothing
        if not is_authenticated:
            response_serializer = self.get_response_serializer(public_agg)
            response =  Response(response_serializer.data)
            patch_response_headers(response, public_cache_timeout)
            return response

        private_cache_key = "agg_private_%s" % blake2b(
            "|".join(
              map(str, cache_key_elms + [request.user.id])
            ).encode("utf-8")
        ).hexdigest()

        private_agg = cache.get(private_cache_key)

        if private_agg is None:
            logger.info("private agg cache miss")
            private_frames = frames.all().filter(public_date__gt=Now())

            user_proposals = None
            if not is_superuser:
                user_proposals = request.user.profile.proposals or []

            private_agg = self._agg_frames_sql(
              private_frames,
              query_timeout,
              user_proposals
            )
            cache.set(private_cache_key, private_agg, private_cache_timeout)
        else:
            logger.info("private agg cache hit")

        union_agg = {}
        for k, v in public_agg.items():
          if k == "generated_at":
              union_agg[k] = private_agg.get(k, "")
              continue

          union_agg[k] = v | private_agg.get(k, set())

        response_serializer = self.get_response_serializer(union_agg)
        response =  Response(response_serializer.data)

        # client can cache the request for at-least as long as the
        # private cache key is valid
        patch_response_headers(response, private_cache_timeout)

        return response

    def _agg_frames_sql(self, *args, **kwargs):
        try:
            r = aggregate_frames_sql(*args, **kwargs)
        except OperationalError:
            logger.exception("filtered aggregation timed out")
            raise APIException(
                "Aggregation query timed out. Either try narrowing the search "
                "space by adding more filters or increase the timeout.",
                599
            )

        return r

    def _agg_frames_all_resp(self):
        logger.info("returning all aggregates from cache")

        response_dict = get_cached_frames_aggregates()

        if not response_dict:
            logger.warn(
                "Cache does not have all aggregates. "
                "Perhaps the management command has not been run yet."
            )
            return Response(
                "Aggregate over everything have not been generated yet. "
                "Try again later.",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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

        frame = get_object_or_404(Frame, pk=pk)
        version = frame.version_set.first()
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


class CatalogViewSet(viewsets.ViewSet):
    schema = ScienceArchiveSchema(tags=['Frames'])

    @action(detail=True)
    def catalog(self, request, pk=None):
        '''
        Instruct the server to download the given Version (one part of a Frame), extract the catalog extension, and
        then return a pared down FITS file to the client
        '''
        logger.info(msg='Downloading file via catalog endpoint')

        frame = get_object_or_404(Frame, pk=pk)
        version = frame.version_set.first()
        file_store = FileStoreFactory.get_file_store_class()()
        path = get_file_store_path(version.frame.filename, version.frame.get_header_dict())

        filename = frame.filename.replace('.fits.fz', '-catalog.fits')

        with file_store.get_fileobj(path) as fileobj:
            frame = fits.open(fileobj)
            with io.BytesIO() as buffer:
                hdulist = fits.HDUList([fits.PrimaryHDU(header=frame['SCI'].header), frame['CAT']])
                hdulist.writeto(buffer)
                buffer.seek(0)

                # return it to the client
                return HttpResponse(buffer.getvalue(), content_type='application/octet-stream',
                                    headers={'Content-Disposition': f'attachment; filename={filename}'})
