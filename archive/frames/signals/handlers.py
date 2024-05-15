from django.dispatch import receiver
from django.db.models.signals import post_delete

from archive.frames.models import Version, Thumbnail


@receiver(post_delete, sender=Version)
def version_post_delete(sender, instance, *args, **kwargs):
    instance.delete_data()

@receiver(post_delete, sender=Thumbnail)
def thumbnail_post_delete(sender, instance, *args, **kwargs):
    instance.delete_data()
