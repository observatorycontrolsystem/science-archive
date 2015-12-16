from archive.frames.models import Frame
from archive.frames.serializers import FrameSerializer
from archive.frames.utils import remove_dashes_from_keys
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


class FrameListView(APIView):
    def get(self, request, format=None):
        frames = Frame.objects.all()
        serializer = FrameSerializer(frames, many=True)
        return Response(serializer.data)

    def post(self, request, format=None):
        data = remove_dashes_from_keys(request.data)
        frame_serializer = FrameSerializer(data=data)
        if frame_serializer.is_valid():
            frame_serializer.save()
            return Response(frame_serializer.data, status=status.HTTP_201_CREATED)
        else:
            print(frame_serializer.errors)
            return Response(frame_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
