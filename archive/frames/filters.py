from archive.frames.models import Frame
from rest_framework_gis.filterset import GeoFilterSet
from rest_framework_gis import filters as geofilters
import django_filters
from datetime import datetime


class FrameFilter(GeoFilterSet):
    start = django_filters.DateTimeFilter(name='DATE_OBS', lookup_type='gte')
    end = django_filters.DateTimeFilter(name='DATE_OBS', lookup_type='lte')
    covers = geofilters.GeometryFilter(name='area', lookup_type='covers')
    intersects = geofilters.GeometryFilter(name='area', lookup_type='intersects')
    basename = django_filters.CharFilter(name='basename', lookup_type='icontains')
    OBJECT = django_filters.CharFilter(name='OBJECT', lookup_type='icontains')
    public = django_filters.MethodFilter(action='public_filter')
    EXPTIME = django_filters.NumberFilter(name='EXPTIME', lookup_type='gte')

    def public_filter(self, queryset, value):
        if value == 'false':
            return queryset.exclude(L1PUBDAT__lt=datetime.utcnow())
        return queryset

    class Meta:
        model = Frame
        fields = ['basename', 'DATE_OBS', 'PROPID', 'OBSTYPE', 'EXPTIME',
                  'INSTRUME', 'OBJECT', 'start', 'end', 'area', 'public',
                  'RLEVEL', 'SITEID', 'TELID', 'FILTER', 'L1PUBDAT', 'BLKUID']
