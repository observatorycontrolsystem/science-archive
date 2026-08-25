from archive.test_helpers import ReplicationTestCase
from django.urls import reverse
from rest_framework import status

import json


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
