from archive.dbrouters import ReadRoutingMiddleware, authenticated_request
from archive.frames.models import Frame
from archive.test_helpers import ReplicationTestCase
from django.contrib.auth.models import AnonymousUser, User
from django.contrib.sessions.models import Session
from django.db import router
from django.http import HttpResponse
from django.test import RequestFactory
from rest_framework.authtoken.models import Token


class TestReadRouting(ReplicationTestCase):
    """
    Reads for anonymous requests go to the reader endpoint so that bot traffic has less
    impact on real users, who are served by the writer.
    """
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create(username='frodo', password='theone')

    def route(self, request):
        """Run a request through the middleware and report where its reads would go"""
        databases = {}

        def get_response(request):
            databases['frame'] = Frame.objects.all().db
            databases['user'] = User.objects.all().db
            return HttpResponse()

        ReadRoutingMiddleware(get_response)(request)
        return databases

    def test_anonymous_request_reads_from_the_replica(self):
        request = self.factory.get('/frames/')
        request.user = AnonymousUser()
        self.assertEqual(self.route(request), {'frame': 'replica', 'user': 'default'})

    def test_authenticated_request_reads_from_the_writer(self):
        request = self.factory.get('/frames/')
        request.user = self.user
        self.assertEqual(self.route(request), {'frame': 'default', 'user': 'default'})

    def test_request_without_a_user_reads_from_the_replica(self):
        self.assertEqual(self.route(self.factory.get('/frames/'))['frame'], 'replica')

    def test_writes_always_go_to_the_writer(self):
        request = self.factory.get('/frames/')
        request.user = AnonymousUser()

        def get_response(request):
            self.assertEqual(router.db_for_write(Frame), 'default')
            return HttpResponse()

        ReadRoutingMiddleware(get_response)(request)

    def test_routing_does_not_leak_between_requests(self):
        authenticated = self.factory.get('/frames/')
        authenticated.user = self.user
        self.route(authenticated)

        self.assertFalse(authenticated_request.get())
        anonymous = self.factory.get('/frames/')
        anonymous.user = AnonymousUser()
        self.assertEqual(self.route(anonymous)['frame'], 'replica')

    def test_routing_is_reset_when_the_view_raises(self):
        request = self.factory.get('/frames/')
        request.user = self.user

        def get_response(request):
            raise ValueError('view exploded')

        with self.assertRaises(ValueError):
            ReadRoutingMiddleware(get_response)(request)

        self.assertFalse(authenticated_request.get())

    def test_login_models_always_use_the_writer(self):
        request = self.factory.get('/frames/')
        request.user = AnonymousUser()

        def get_response(request):
            # A session and its user are read back on the request right after logging in,
            # which is sooner than they can be expected to have replicated
            for model in (Session, User):
                self.assertEqual(router.db_for_read(model), 'default', model.__name__)
            # API tokens only change when a user regenerates one by hand, so the reader is
            # current enough for them
            self.assertEqual(router.db_for_read(Token), 'replica')
            return HttpResponse()

        ReadRoutingMiddleware(get_response)(request)

    def test_reads_outside_the_request_cycle_use_the_replica(self):
        # Management commands and workers keep reading from the reader as they always have
        self.assertEqual(Frame.objects.all().db, 'replica')
