from archive.frames.models import Frame
from archive.frames.serializers import FrameSerializer
from archive.frames.utils import remove_dashes_from_keys, fits_keywords_only
from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status
from rest_framework import filters
import logging

logger = logging.getLogger()


class FrameListView(generics.ListCreateAPIView):
    queryset = Frame.objects.all()
    serializer_class = FrameSerializer
    filter_backends = (
        filters.DjangoFilterBackend,
        filters.OrderingFilter,
    )
    filter_fields = ('id', 'filename', 'DATE_OBS', 'USERID',
                     'PROPID', 'INSTRUME', 'OBJECT')
    ordering_fields = ('id', 'filename', 'DATE_OBS', 'USERID',
                       'PROPID', 'INSTRUME', 'OBJECT')

    def post(self, request, format=None):
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


class FrameView(generics.RetrieveAPIView):
    queryset = Frame.objects.all()
    serializer_class = FrameSerializer
