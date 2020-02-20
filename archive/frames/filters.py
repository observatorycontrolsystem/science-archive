from archive.frames.models import Frame
from django.contrib.gis.geos import GEOSGeometry
from django.utils import timezone
from django_filters import rest_framework as django_filters


class FrameFilter(django_filters.FilterSet):
    start = django_filters.DateTimeFilter(field_name='DATE_OBS', lookup_expr='gte')
    end = django_filters.DateTimeFilter(field_name='DATE_OBS', lookup_expr='lte')
    dayobs = django_filters.DateFilter(field_name='DAY_OBS', lookup_expr='iexact')
    basename = django_filters.CharFilter(field_name='basename', lookup_expr='icontains')
    OBJECT = django_filters.CharFilter(field_name='OBJECT', lookup_expr='icontains')
    public = django_filters.BooleanFilter(field_name='public', method='public_filter')
    EXPTIME = django_filters.NumberFilter(field_name='EXPTIME', lookup_expr='gte')
    covers = django_filters.CharFilter(method='covers_filter')
    OBSTYPE = django_filters.MultipleChoiceFilter(field_name='OBSTYPE', choices=Frame.OBSERVATION_TYPES)
    exclude_OBSTYPE = django_filters.MultipleChoiceFilter(
        field_name='OBSTYPE',
        choices=Frame.OBSERVATION_TYPES,
        label='Exclude Obstypes',
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
            return queryset.exclude(L1PUBDAT__lt=timezone.now())
        return queryset

    class Meta:
        model = Frame
        fields = ['DATE_OBS', 'DAY_OBS', 'PROPID', 'OBSTYPE', 'INSTRUME',
                  'RLEVEL', 'SITEID', 'TELID', 'FILTER', 'L1PUBDAT',
                  'BLKUID', 'REQNUM']
