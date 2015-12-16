from rest_framework import serializers
from archive.frames.models import Frame, Version


class VersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Version
        fields = ('id', 'timestamp', 'key', 'md5')


class FrameSerializer(serializers.ModelSerializer):
    filename = serializers.CharField(required=True)
    version_set = VersionSerializer(many=True)
    area = serializers.ListField(
        child=serializers.ListField(
            child=serializers.FloatField()
        )
    )

    class Meta:
        model = Frame
        fields = (
            'id', 'filename', 'area', 'related_frames', 'version_set',
            'DATE_OBS', 'USERID', 'PROPID', 'INSTRUME',
            'OBJECT', 'SITEID', 'TELID', 'EXPTIME', 'FILTER',
            'L1PUBDAT', 'OBSTYPE',
        )

    def create(self, validated_data):
        try:
            frame = Frame.objects.get(filename=validated_data['filename'])
        except Frame.DoesNotExist:
            frame = Frame(filename=validated_data['filename'])
        frame.area = tuple([tuple(x) for x in validated_data['area']])
        for field in ['DATE_OBS', 'USERID', 'PROPID', 'INSTRUME',
                      'OBJECT', 'SITEID', 'TELID', 'EXPTIME', 'FILTER',
                      'L1PUBDAT', 'OBSTYPE']:
                        setattr(frame, field, validated_data[field])
        frame.save()
        for version in self.validated_data['version_set']:
            Version.objects.create(frame=frame, **version)
        return frame
