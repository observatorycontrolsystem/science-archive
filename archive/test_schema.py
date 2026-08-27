from archive.schema import PYPROJECT_PATH, get_archive_version
from archive.test_helpers import ReplicationTestCase
from django.urls import reverse
from rest_framework import status
from unittest.mock import patch

import json
import tomllib


class TestOpenApiSchema(ReplicationTestCase):
    """
    Test that the OpenAPI schema generation works
    """
    def get_schema(self):
        response = self.client.get(reverse('openapi-schema'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return json.loads(response.content)

    def test_schema_documents_every_endpoint(self):
        schema = self.get_schema()
        for path in ('/frames/', '/frames/{id}/', '/frames/aggregate/', '/frames/zip/',
                     '/thumbnails/', '/versions/', '/profile/'):
            self.assertIn(path, schema['paths'])

    def test_schema_documents_frame_filters(self):
        parameters = {p['name'] for p in self.get_schema()['paths']['/frames/']['get']['parameters']}
        # Filters come from the filterset, pagination and ordering from their backends
        for parameter in ('start', 'end', 'covers', 'exclude_calibrations', 'limit', 'offset', 'ordering'):
            self.assertIn(parameter, parameters)

    def test_schema_documents_the_ordering_restriction(self):
        parameters = self.get_schema()['paths']['/frames/']['get']['parameters']
        ordering = next(p for p in parameters if p['name'] == 'ordering')
        self.assertIn('observation_date', ordering['description'])

    def test_schema_reports_the_release_version(self):
        with open(PYPROJECT_PATH, 'rb') as pyproject:
            expected = tomllib.load(pyproject)['tool']['poetry']['version']
        self.assertEqual(self.get_schema()['info']['version'], expected)

    def test_schema_generates_without_a_version_to_report(self):
        # The deployed image has no .git and could have no pyproject.toml either, which used to
        # take the whole endpoint down rather than just the version string
        with patch('archive.schema.PYPROJECT_PATH', '/nonexistent/pyproject.toml'):
            self.assertEqual(get_archive_version(), 'unknown')
            self.assertEqual(self.get_schema()['info']['version'], 'unknown')
