from django.dispatch import receiver
from django.db.models.signals import post_delete, post_save
from django.conf import settings
from kombu.connection import Connection
from kombu import Exchange, Queue

from archive.frames.models import Version
from archive.frames.serializers import FrameSerializer


@receiver(post_delete, sender=Version)
def version_post_delete(sender, instance, *args, **kwargs):
    instance.delete_data()


@receiver(post_save, sender=Version)
def version_post_save(sender, instance, created, *args, **kwargs):
    post_to_archived_queue(instance)


def post_to_archived_queue(version):
    broker_url = settings.QUEUE_BROKER_URL
    processed_exchange = Exchange(settings.PROCESSED_EXCHANGE_NAME, type='fanout')
    producer_queue = Queue('', processed_exchange, exclusive=True)
    payload = FrameSerializer(version.frame).data
    payload['frameid'] = payload['id']  # preserve backwards compatibility with ingester
    payload['DATE-OBS'] = payload['DATE_OBS']  # preserve backwards compatibility with ingester
    with Connection(broker_url) as conn:
        queue = conn.SimpleQueue(producer_queue)
        queue.put(payload)
        queue.close()
