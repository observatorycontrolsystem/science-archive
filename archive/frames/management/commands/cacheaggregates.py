from django.core.management.base import BaseCommand

from archive.frames.models import Frame
from archive.frames.utils import (
    set_cached_frames_aggregates, aggregate_frames_sql
)


class Command(BaseCommand):

    help = "Generates and caches aggregates over all frames"

    def handle(self, *args, **options):
        self.stdout.write("Aggregating...")
        resp = aggregate_frames_sql(Frame.objects.all())

        self.stdout.write("Updating cache...")
        set_cached_frames_aggregates(resp)

        self.stdout.write(self.style.SUCCESS("Successfully updated cache"))
