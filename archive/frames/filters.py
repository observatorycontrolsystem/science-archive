from archive.frames.models import Frame
from django.contrib.gis.geos import GEOSGeometry
from django.utils import timezone
from django_filters import rest_framework as django_filters


class FrameFilter(django_filters.FilterSet):
    start = django_filters.DateTimeFilter(field_name='observation_date', lookup_expr='gte')
    end = django_filters.DateTimeFilter(field_name='observation_date', lookup_expr='lte')
    dayobs = django_filters.DateFilter(field_name='observation_day', lookup_expr='iexact')
    basename = django_filters.CharFilter(field_name='basename', lookup_expr='icontains')
    OBJECT = django_filters.CharFilter(field_name='target_name', lookup_expr='icontains')
    target_name = django_filters.CharFilter(field_name='target_name', lookup_expr='icontains')
    public = django_filters.BooleanFilter(field_name='public', method='public_filter')
    EXPTIME = django_filters.NumberFilter(field_name='exposure_time', lookup_expr='gte')
    exposure_time = django_filters.NumberFilter(field_name='exposure_time', lookup_expr='gte')
    OBSTYPE = django_filters.CharFilter(field_name='configuration_type', lookup_expr='icontains')
    PROPID = django_filters.CharFilter(field_name='proposal_id', lookup_expr='icontains')
    INSTRUME = django_filters.CharFilter(field_name='instrument_id', lookup_expr='icontains')
    SITEID = django_filters.CharFilter(field_name='site_id', lookup_expr='icontains')
    TELID = django_filters.CharFilter(field_name='telescope_id', lookup_expr='icontains')
    FILTER = django_filters.CharFilter(field_name='primary_filter', lookup_expr='icontains')
    BLKUID = django_filters.NumberFilter(field_name='observation_id', lookup_expr='exact')
    REQNUM = django_filters.NumberFilter(field_name='request_id', lookup_expr='exact')
    RLEVEL = django_filters.NumberFilter(field_name='reduction_level', lookup_expr='exact')
    covers = django_filters.CharFilter(method='covers_filter')
    exclude_OBSTYPE = django_filters.MultipleChoiceFilter(
        field_name='configuration_type',
        choices=Frame.OBSERVATION_TYPES,
        label='Exclude Configuration Types',
        exclude=True
    )
    exclude_configuration_type = django_filters.MultipleChoiceFilter(
        field_name='configuration_type',
        choices=Frame.OBSERVATION_TYPES,
        label='Exclude Configuration Types',
        exclude=True
    )
    intersects = django_filters.CharFilter(method='intersects_filter')

    def covers_filter(self, queryset, name, value):
        geo = GEOSGeometry(value)
        return queryset.filter(area__covers=geo)

    def intersects_filter(self, queryset, name, value):
        geo = GEOSGeometry(value)
        return queryset.filter(area__intersects=geo)

    def public_filter(self, queryset, name, value):
        if not value:
            return queryset.exclude(public_date__lt=timezone.now())
        return queryset

    class Meta:
        model = Frame
        fields = ['proposal_id', 'configuration_type', 'instrument_id',
                  'reduction_level', 'site_id', 'telescope_id', 'primary_filter',
                  'observation_id', 'request_id']
