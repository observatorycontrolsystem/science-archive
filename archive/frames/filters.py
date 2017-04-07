from archive.frames.models import Frame
from django.contrib.gis.geos import GEOSGeometry
from django.utils import timezone
import django_filters


class FrameFilter(django_filters.FilterSet):
    start = django_filters.DateTimeFilter(name='DATE_OBS', lookup_expr='gte')
    end = django_filters.DateTimeFilter(name='DATE_OBS', lookup_expr='lte')
    basename = django_filters.CharFilter(name='basename', lookup_expr='icontains')
    OBJECT = django_filters.CharFilter(name='OBJECT', lookup_expr='icontains')
    public = django_filters.CharFilter(method='public_filter')
    EXPTIME = django_filters.NumberFilter(name='EXPTIME', lookup_expr='gte')
    covers = django_filters.CharFilter(method='covers_filter')
    intersects = django_filters.CharFilter(method='intersects_filter')

    def covers_filter(self, queryset, name, value):
        geo = GEOSGeometry(value)
        return queryset.filter(area__covers=geo)

    def intersects_filter(self, queryset, name, value):
        geo = GEOSGeometry(value)
        return queryset.filter(area__intersects=geo)

    def public_filter(self, queryset, name, value):
        if value == 'false':
            return queryset.exclude(L1PUBDAT__lt=timezone.now())
        return queryset

    class Meta:
        model = Frame
        fields = ['DATE_OBS', 'PROPID', 'OBSTYPE', 'INSTRUME',
                  'RLEVEL', 'SITEID', 'TELID', 'FILTER', 'L1PUBDAT',
                  'BLKUID', 'REQNUM']
