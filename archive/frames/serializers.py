from rest_framework import serializers
from archive.frames.models import Frame, Version, Headers


class ZipSerializer(serializers.Serializer):
    frame_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1)
    )


class VersionSerializer(serializers.ModelSerializer):
    url = serializers.CharField(read_only=True)

    class Meta:
        model = Version
        fields = ('id', 'created', 'key', 'md5', 'extension', 'url')


class FrameSerializer(serializers.ModelSerializer):
    basename = serializers.CharField(required=True)
    version_set = VersionSerializer(many=True)
    url = serializers.CharField(read_only=True)
    filename = serializers.CharField(read_only=True)
    related_frames = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Frame.objects.exclude(version=None),
        required=False,
        style={'base_template': 'input.html'}
    )

    class Meta:
        model = Frame
        fields = (
            'id', 'basename', 'area', 'related_frames', 'version_set',
            'filename', 'url', 'RLEVEL', 'DATE_OBS', 'PROPID', 'INSTRUME',
            'OBJECT', 'SITEID', 'TELID', 'EXPTIME', 'FILTER',
            'L1PUBDAT', 'OBSTYPE',
        )

    def create(self, validated_data):
        version_data = validated_data.pop('version_set')
        header_data = validated_data.pop('header')
        frame = self.create_or_update_frame(validated_data)
        self.create_or_update_versions(frame, version_data)
        self.create_or_update_header(frame, header_data)
        self.create_related_frames(frame, header_data)
        return frame

    def create_or_update_frame(self, data):
        frame, created = Frame.objects.update_or_create(defaults=data, basename=data['basename'])
        return frame

    def create_or_update_versions(self, frame, data):
        for version in data:
            Version.objects.create(frame=frame, **version)

    def create_or_update_header(self, frame, data):
        header, created = Headers.objects.update_or_create(defaults={'data': data}, frame=frame)

    def create_related_frames(self, frame, data):
        related_frame_keys = [
            'L1IDBIAS', 'L1IDDARK', 'L1IDFLAT', 'L1IDSHUT',
            'L1IDMASK', 'L1IDFRNG', 'L1IDCAT', 'TARFILE',
        ]
        for key in related_frame_keys:
            related_frame = data.get(key)
            if related_frame:
                rf, created = Frame.objects.get_or_create(basename=related_frame)
                frame.related_frames.add(rf)
        frame.save()
