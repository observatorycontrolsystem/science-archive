from archive.frames.models import Frame
from rest_framework_gis.filterset import GeoFilterSet
from rest_framework_gis import filters as geofilters
import django_filters


class FrameFilter(GeoFilterSet):
    start = django_filters.DateTimeFilter(name='DATE_OBS', lookup_type='gte')
    end = django_filters.DateTimeFilter(name='DATE_OBS', lookup_type='lte')
    covers = geofilters.GeometryFilter(name='area', lookup_type='covers')

    class Meta:
        model = Frame
        fields = ['basename', 'DATE_OBS', 'PROPID', 'OBSTYPE',
                  'INSTRUME', 'OBJECT', 'start', 'end', 'area',
                  'RLEVEL', 'SITEID', 'TELID', 'FILTER']
