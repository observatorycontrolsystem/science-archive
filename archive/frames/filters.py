from archive.frames.models import Frame
from archive.frames.utils import get_configuration_type_tuples
from archive.settings import SCIENCE_CONFIGURATION_TYPES
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.geos.error import GEOSException
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from django_filters import rest_framework as django_filters


class FrameFilter(django_filters.FilterSet):
    # TODO: Remove all uppercase old filter names once users have had a change to migrate
    start = django_filters.DateTimeFilter(field_name='observation_date', lookup_expr='gte')
    end = django_filters.DateTimeFilter(field_name='observation_date', lookup_expr='lte')
    DATE_OBS = django_filters.DateTimeFilter(field_name='observation_date')
    DAY_OBS = django_filters.DateFilter(field_name='observation_day')
    dayobs = django_filters.DateFilter(field_name='observation_day')
    basename = django_filters.CharFilter(field_name='basename', lookup_expr='icontains')
    basename_exact = django_filters.CharFilter(field_name='basename', lookup_expr='exact')
    OBJECT = django_filters.CharFilter(field_name='target_name', lookup_expr='icontains')
    target_name = django_filters.CharFilter(field_name='target_name', lookup_expr='icontains')
    target_name_exact = django_filters.CharFilter(field_name='target_name', lookup_expr='exact')
    L1PUBDAT = django_filters.DateTimeFilter(field_name='public_date')
    public = django_filters.BooleanFilter(field_name='public', method='public_filter')
    EXPTIME = django_filters.NumberFilter(field_name='exposure_time', lookup_expr='gte')
    exposure_time = django_filters.NumberFilter(field_name='exposure_time', lookup_expr='gte')
    OBSTYPE = django_filters.CharFilter(field_name='configuration_type', lookup_expr='exact')
    PROPID = django_filters.CharFilter(field_name='proposal_id', lookup_expr='exact')
    INSTRUME = django_filters.CharFilter(field_name='instrument_id', lookup_expr='exact')
    SITEID = django_filters.CharFilter(field_name='site_id', lookup_expr='exact')
    TELID = django_filters.CharFilter(field_name='telescope_id', lookup_expr='exact')
    FILTER = django_filters.CharFilter(field_name='primary_optical_element', lookup_expr='exact')
    BLKUID = django_filters.NumberFilter(field_name='observation_id', lookup_expr='exact')
    REQNUM = django_filters.NumberFilter(field_name='request_id', lookup_expr='exact')
    RLEVEL = django_filters.NumberFilter(field_name='reduction_level', lookup_expr='exact')
    covers = django_filters.CharFilter(method='covers_filter')
    exclude_OBSTYPE = django_filters.MultipleChoiceFilter(
        field_name='configuration_type',
        choices=get_configuration_type_tuples(),
        label='Exclude Configuration Types',
        exclude=True
    )
    exclude_configuration_type = django_filters.MultipleChoiceFilter(
        field_name='configuration_type',
        choices=get_configuration_type_tuples(),
        label='Exclude Configuration Types',
        exclude=True
    )
    include_configuration_type = django_filters.MultipleChoiceFilter(
        field_name='configuration_type',
        choices=get_configuration_type_tuples(),
        label='Include Configuration Types',
    )
    exclude_calibrations = django_filters.BooleanFilter(field_name='exclude_calibrations', method='exclude_calibrations_filter')
    intersects = django_filters.CharFilter(method='intersects_filter')

    def covers_filter(self, queryset, name, value):
        try:
            geo = GEOSGeometry(value)
        except GEOSException:
            raise ValidationError("Error with covers query: Point must be specified with exact format 'POINT(RA DEC)'")
        return queryset.filter(area__covers=geo)

    def intersects_filter(self, queryset, name, value):
        try:
            geo = GEOSGeometry(value)
        except GEOSException:
            raise ValidationError("Error with intersects query: Point must be specified with exact format 'POINT(RA DEC)'")
        return queryset.filter(area__intersects=geo)

    def public_filter(self, queryset, name, value):
        if not value:
            if self.request.user.is_authenticated and not self.request.user.is_superuser:
                user_proposals = self.request.user.profile.proposals
                if user_proposals:
                    return queryset.filter(proposal_id__in=user_proposals)
            else:
                return queryset.exclude(public_date__lt=timezone.now())
        return queryset

    def exclude_calibrations_filter(self, queryset, name, value):
        if value:
            return queryset.filter(configuration_type__in=SCIENCE_CONFIGURATION_TYPES)
        return queryset

    class Meta:
        model = Frame
        fields = ['proposal_id', 'configuration_type', 'instrument_id',
                  'reduction_level', 'site_id', 'telescope_id', 'primary_optical_element',
                  'observation_id', 'request_id']
