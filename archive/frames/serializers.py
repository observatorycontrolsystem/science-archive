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
        version_data = validated_data.pop('version_set')
        try:
            frame = Frame.objects.get(filename=validated_data['filename'])
            frame = Frame(id=frame.id, **validated_data)
        except Frame.DoesNotExist:
            frame = Frame(**validated_data)
        frame.save()
        for version in version_data:
            Version.objects.create(frame=frame, **version)
        return frame
