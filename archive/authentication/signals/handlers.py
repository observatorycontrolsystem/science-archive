from django.dispatch import receiver
from django.db.models.signals import post_save
from django.contrib.auth.models import User

from archive.authentication.models import Profile


@receiver(post_save, sender=User)
def cb_user_post_save(sender, instance, created, *args, **kwargs):
    # If a new user is created, ensure it as a profile set
    if created:
        Profile.objects.get_or_create(user=instance)
