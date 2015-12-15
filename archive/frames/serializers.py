from rest_framework import serializers
from archive.frames.models import Frame, Version


class VersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Version
        fields = ('id', 'timestamp', 'key', 'md5')

    def create(self, validated_data):
        print(validated_data)
        version = Version.objects.create(**validated_data)
        return version


class FrameSerializer(serializers.ModelSerializer):
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
        validated_data['area'] = tuple([tuple(x) for x in validated_data['area']])
        frame = Frame.objects.create(**validated_data)
        for version in version_data:
            Version.objects.create(frame=frame, **version)
        return frame
