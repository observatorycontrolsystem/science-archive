import json
from rest_framework import serializers
from archive.frames.models import Frame, Version, Headers
from django.contrib.gis.geos import GEOSGeometry
from django.db import transaction


class ZipSerializer(serializers.Serializer):
    frame_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1)
    )
    uncompress = serializers.BooleanField(default=False)


class VersionSerializer(serializers.ModelSerializer):
    url = serializers.CharField(read_only=True)

    class Meta:
        model = Version
        fields = ('id', 'created', 'key', 'md5', 'extension', 'url')


class HeadersSerializer(serializers.ModelSerializer):
    class Meta:
        model = Headers
        fields = ('data',)


class PolygonField(serializers.Field):
    def to_representation(self, obj):
        return json.loads(obj.geojson)

    def to_internal_value(self, data):
        try:
            return GEOSGeometry(json.dumps(data))
        except:
            raise serializers.ValidationError('Invalid polygon: {0}'.format(data))


class FrameSerializer(serializers.ModelSerializer):
    basename = serializers.CharField(required=True)
    version_set = VersionSerializer(many=True)
    url = serializers.CharField(read_only=True)
    filename = serializers.CharField(read_only=True)
    area = PolygonField(allow_null=True)
    DAY_OBS = serializers.DateField(input_formats=['iso-8601', '%Y%m%d'])
    related_frames = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Frame.objects.exclude(DATE_OBS=None),
        required=False,
        style={'base_template': 'input.html'}
    )

    class Meta:
        model = Frame
        fields = (
            'id', 'basename', 'area', 'related_frames', 'version_set',
            'filename', 'url', 'RLEVEL', 'DAY_OBS', 'DATE_OBS', 'PROPID',
            'INSTRUME', 'OBJECT', 'SITEID', 'TELID', 'EXPTIME', 'FILTER',
            'L1PUBDAT', 'OBSTYPE', 'BLKUID', 'REQNUM',
        )

    def create(self, validated_data):
        version_data = validated_data.pop('version_set')
        header_data = validated_data.pop('header')
        with transaction.atomic():
            frame = self.create_or_update_frame(validated_data)
            self.create_or_update_versions(frame, version_data)
            self.create_or_update_header(frame, header_data)
            self.create_related_frames(frame, header_data)
        return frame

    def create_or_update_frame(self, data):
        frame, _ = Frame.objects.update_or_create(defaults=data, basename=data['basename'])
        return frame

    def create_or_update_versions(self, frame, data):
        for version in data:
            Version.objects.create(frame=frame, **version)

    def create_or_update_header(self, frame, data):
        Headers.objects.update_or_create(defaults={'data': data}, frame=frame)

    def create_related_frames(self, frame, data):
        related_frame_keys = [
            'L1IDBIAS', 'L1IDDARK', 'L1IDFLAT', 'L1IDSHUT',
            'L1IDMASK', 'L1IDFRNG', 'L1IDCAT', 'TARFILE',
            'ORIGNAME', 'L1IDARC', 'L1IDTMPL', 'L1IDTRAC',
        ]
        for key in related_frame_keys:
            related_frame = data.get(key)
            if related_frame and related_frame != frame.basename:
                rf, _ = Frame.objects.get_or_create(basename=related_frame)
                frame.related_frames.add(rf)
        frame.save()
