from rest_framework.schemas.openapi import AutoSchema, SchemaGenerator
from rest_framework import serializers
from rest_framework.schemas.utils import is_list_view
from setuptools_scm import get_version
from setuptools_scm.version import ScmVersion
from django.conf import settings
from django_filters.rest_framework import DjangoFilterBackend

import logging
logger = logging.getLogger(__name__)


def version_scheme(version: ScmVersion) -> str:
    """Simply return the string representation of the version object tag, which is the latest git tag.
    setuptools_scm does not provide a simple semantic versioning format without trying to guess the next release, or adding some metadata to the version.
    """
    return str(version.tag)


class DocumentedDjangoFilterBackend(DjangoFilterBackend):
    """
    django-filter dropped DRF schema support in 25.1 (DRF's own schema generation is
    deprecated in favour of drf-spectacular), but DRF's AutoSchema still calls
    get_schema_operation_parameters() on every filter backend, so schema generation raises
    an AttributeError without this.
    """
    def get_schema_operation_parameters(self, view):
        # Views with no filters have nothing to document, so ignore them
        if not getattr(view, 'filterset_class', None) and not getattr(view, 'filterset_fields', None):
            return []

        try:
            queryset = view.get_queryset()
        except Exception:
            queryset = None
            logger.warning(f'{view.__class__} is not compatible with schema generation')

        filterset_class = self.get_filterset_class(view, queryset)
        if not filterset_class:
            return []

        return [
            {
                'name': field_name,
                'required': field.extra['required'],
                'in': 'query',
                'description': field.label if field.label is not None else field_name,
                'schema': {
                    'type': 'string',
                },
            }
            for field_name, field in filterset_class.base_filters.items()
        ]


class ScienceArchiveSchemaGenerator(SchemaGenerator):
    def get_schema(self, *args, **kwargs):
        schema = super().get_schema(*args, **kwargs)
        schema['info']['title'] = settings.NAVBAR_TITLE_TEXT
        schema['info']['description'] = 'API documentation for the OCS Science Archive'
        schema['info']['version'] = get_version(version_scheme=version_scheme, local_scheme='no-local-version')
        return schema


class ScienceArchiveSchema(AutoSchema):
    def __init__(self, tags=None, operation_id_base=None, component_name=None, empty_request=False):
        super().__init__(tags=tags, operation_id_base=operation_id_base, component_name=component_name)
        self.empty_request = empty_request

    def get_operation_id(self, path, method):
        """
        This method is used to determine the descriptive name of the endpoint displayed in the documentation.
        Allow this to be overridden in the view - a view that defines get_endpoint_name can override the default
        DRF naming scheme.
        """
        operation_id = super().get_operation_id(path, method)
        if getattr(self.view, 'get_endpoint_name', None) is not None:
            name_override = self.view.get_endpoint_name()
            # For some viewsets, we may not have specified a name for an action - guard against that
            if name_override is not None:
                operation_id = name_override

        return operation_id

    def get_operation(self, path, method):
        """
        This method is used to determine, among other things, the request and response bodies for a particular endpoint.
        We override this to support specifying our own request and response bodies. Any view that implements get_example_response
        and/or get_example_request can provide their own custom request and response bodies to display in the OpenAPI docs.
        """
        operations =  super().get_operation(path, method)
        # If the view has implemented get_example_response, then use it to present in the documentation
        if getattr(self.view, 'get_example_response', None) is not None:
            example_response = self.view.get_example_response()
            # For viewsets, not all actions may have example responses defined, so this method may return None
            if example_response is not None:
                status_code = example_response.status_code
                example_data = example_response.data
                content_type = example_response.content_type if example_response.content_type is not None else 'application/json'
                operations['responses'] = {status_code: {'content': {content_type: {'example': example_data}}}}

        # If the view has implemented get_example_request, then use it to present in the documentation
        if getattr(self.view, 'get_example_request', None) is not None:
            example_request = self.view.get_example_request()
            if example_request is not None:
                operations['requestBody']['content']['application/json']['example'] = example_request

        if self.empty_request:
            operations['requestBody'] = {}

        return operations

    def get_filter_parameters(self, path, method):
        if getattr(self.view, 'get_query_parameters', None) is not None:
            override_query_parameters = self.view.get_query_parameters()
            if override_query_parameters is not None:
                return override_query_parameters

        return super().get_filter_parameters(path, method)

    def get_request_serializer(self, path, method):
        view = self.view

        if not hasattr(view, 'get_request_serializer'):
            if not hasattr(view, 'get_serializer'):
                # If this view doesn't have a serializer, then we can't auto-document this endpoint
                return None
            else:
                return view.get_serializer()
        else:
            return view.get_request_serializer()

    def get_response_serializer(self, path, method):
        view = self.view

        if not hasattr(view, 'get_response_serializer'):
            if not hasattr(view, 'get_serializer'):
                # If this view doesn't have a serializer, then we can't auto-document this endpoint
                return None
            else:
                return view.get_serializer()
        else:
            return view.get_response_serializer()
