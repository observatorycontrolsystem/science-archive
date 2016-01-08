from rest_framework import serializers
from archive.frames.models import Frame, Version, Headers


class VersionSerializer(serializers.ModelSerializer):
    url = serializers.CharField(read_only=True)

    class Meta:
        model = Version
        fields = ('id', 'timestamp', 'key', 'md5', 'url')


class FrameSerializer(serializers.ModelSerializer):
    filename = serializers.CharField(required=True)
    version_set = VersionSerializer(many=True)
    url = serializers.CharField(read_only=True)
    area = serializers.ListField(
        child=serializers.ListField(
            child=serializers.FloatField()
        ),
        allow_null=True
    )
    related_frames = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Frame.objects.all(),
        required=False,
        style={'base_template': 'input.html'}
    )

    class Meta:
        model = Frame
        fields = (
            'id', 'filename', 'area', 'related_frames', 'version_set',
            'url', 'RLEVEL', 'DATE_OBS', 'USERID', 'PROPID', 'INSTRUME',
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
        frame, created = Frame.objects.update_or_create(defaults=data, filename=data['filename'])
        return frame

    def create_or_update_versions(self, frame, data):
        for version in data:
            Version.objects.create(frame=frame, **version)

    def create_or_update_header(self, frame, data):
        header, created = Headers.objects.update_or_create(defaults={'data': data}, frame=frame)

    def create_related_frames(self, frame, data):
        related_frame_keys = [
            'L1IDBIAS', 'L1IDDARK', 'L1IDFLAT', 'L1IDSHUT', 'L1IDMASK' 'L1IDFRNG', 'L1IDCAT'
        ]
        for key in related_frame_keys:
            filename = data.get(key)
            if filename and filename != 'N/A':
                rf, created = Frame.objects.get_or_create(filename='{}.fits'.format(filename))
                frame.related_frames.add(rf)
        frame.save()
