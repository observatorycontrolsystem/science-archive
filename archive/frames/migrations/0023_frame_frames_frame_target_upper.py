from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models
from django.db.models.functions import Upper


class Migration(migrations.Migration):
    # Built concurrently so the index does not hold a lock against frame ingestion for the
    # length of the build. CREATE INDEX CONCURRENTLY cannot run inside a transaction.
    atomic = False

    dependencies = [
        ('frames', '0022_remove_frame_frames_frame_aggregate_and_more'),
    ]

    operations = [
        AddIndexConcurrently(
            model_name='frame',
            index=models.Index(Upper('target_name'), name='frames_frame_target_upper'),
        ),
    ]
