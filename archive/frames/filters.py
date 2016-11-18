from archive.frames.models import Frame
from rest_framework_gis.filterset import GeoFilterSet
from rest_framework_gis import filters as geofilters
from django.utils import timezone
import django_filters


class FrameFilter(GeoFilterSet):
    start = django_filters.DateTimeFilter(name='DATE_OBS', lookup_expr='gte')
    end = django_filters.DateTimeFilter(name='DATE_OBS', lookup_expr='lte')
    covers = geofilters.GeometryFilter(name='area', lookup_expr='covers')
    intersects = geofilters.GeometryFilter(name='area', lookup_expr='intersects')
    basename = django_filters.CharFilter(name='basename', lookup_expr='icontains')
    OBJECT = django_filters.CharFilter(name='OBJECT', lookup_expr='icontains')
    public = django_filters.CharFilter(method='public_filter')
    EXPTIME = django_filters.NumberFilter(name='EXPTIME', lookup_expr='gte')

    def public_filter(self, queryset, name, value):
        if value == 'false':
            return queryset.exclude(L1PUBDAT__lt=timezone.now())
        return queryset

    class Meta:
        model = Frame
        fields = ['DATE_OBS', 'PROPID', 'OBSTYPE', 'INSTRUME',
                  'RLEVEL', 'SITEID', 'TELID', 'FILTER', 'L1PUBDAT',
                  'BLKUID', 'REQNUM']
