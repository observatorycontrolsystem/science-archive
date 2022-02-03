import json
from rest_framework import serializers
from archive.frames.models import Frame, Version, Headers
from django.contrib.gis.geos import GEOSGeometry
from django.db import transaction


class ZipSerializer(serializers.Serializer):
    frame_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        help_text='Frame IDs of images to include in zip archive'
    )
    uncompress = serializers.BooleanField(
        default=False,
        help_text='Whether to uncompress the FITS files prior to creating zip archive'
    )

    def validate(self, data):
        selected_frames_count = len(data.get('frame_ids', []))
        uncompress = data.get('uncompress', False)
        if uncompress and selected_frames_count > 10:
            raise serializers.ValidationError('A maximum of 10 frames can be downloaded with the uncompress flag. '
                                              'Please try again with fewer frame_ids.')
        return data


class VersionSerializer(serializers.ModelSerializer):
    url = serializers.CharField(read_only=True, help_text='Download URL for given version')

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
    basename = serializers.CharField(required=True, help_text='File basename without extension')
    version_set = VersionSerializer(many=True, help_text='Set of versions associated with this file')
    url = serializers.CharField(read_only=True, help_text='File download URL associated with most recent version')
    filename = serializers.CharField(read_only=True, help_text='Full filename')
    area = PolygonField(allow_null=True, help_text='GeoJSON area that this frame covers')
    DAY_OBS = serializers.DateField(input_formats=['iso-8601', '%Y%m%d'], help_text='Observation day in %Y%m%d format')
    related_frames = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Frame.objects.exclude(DATE_OBS=None),
        required=False,
        style={'base_template': 'input.html'},
        help_text='Set of related frames for this file'
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
        #TODO: Remove this part setting the new fields in the later branch
        if 'DAY_OBS' in data:
            data['observation_day'] = data['DAY_OBS']
        if 'DATE_OBS' in data:
            data['observation_date'] = data['DATE_OBS']
        if 'L1PUBDAT' in data:
            data['public_date'] = data['L1PUBDAT']
        if 'RLEVEL' in data:
            data['reduction_level'] = data['RLEVEL']
        if 'INSTRUME' in data:
            data['instrument_id'] = data['INSTRUME']
        if 'OBJECT' in data:
            data['target_name'] = data['OBJECT']
        if 'SITEID' in data:
            data['site_id'] = data['SITEID']
        if 'TELID' in data:
            data['telescope_id'] = data['TELID']
        if 'EXPTIME' in data:
            data['exposure_time'] = data['EXPTIME']
        if 'FILTER' in data:
            data['primary_optical_element'] = data['FILTER']
        if 'PROPID' in data:
            data['proposal_id'] = data['PROPID']
        if 'OBSTYPE' in data:
            data['configuration_type'] = data['OBSTYPE']
        if 'BLKUID' in data:
            data['observation_id'] = data['BLKUID']
        if 'REQNUM' in data:
            data['request_id'] = data['REQNUM']
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


class AggregateSerializer(serializers.Serializer):
    sites = serializers.ListField(child=serializers.CharField())
    telescopes = serializers.ListField(child=serializers.CharField())
    filters = serializers.ListField(child=serializers.CharField())
    instruments = serializers.ListField(child=serializers.CharField())
    obstypes = serializers.ListField(child=serializers.CharField())
    proposals = serializers.ListField(child=serializers.CharField())
