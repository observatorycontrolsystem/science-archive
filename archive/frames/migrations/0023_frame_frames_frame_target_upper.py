from django.db import migrations, models
from django.db.models.functions import Upper


class Migration(migrations.Migration):
    # Built concurrently so the index does not hold a lock against frame ingestion for the
    # length of the build. CREATE INDEX CONCURRENTLY cannot run inside a transaction.
    atomic = False

    dependencies = [
        ('frames', '0022_remove_frame_frames_frame_aggregate_and_more'),
    ]

    # IF NOT EXISTS so the index can be built by hand ahead of a deploy on large databases, in
    # which case this just records the migration as applied.
    operations = [
        migrations.RunSQL(
            sql='CREATE INDEX CONCURRENTLY IF NOT EXISTS "frames_frame_target_upper" '
                'ON "frames_frame" ((UPPER("target_name")))',
            reverse_sql='DROP INDEX CONCURRENTLY IF EXISTS "frames_frame_target_upper"',
            state_operations=[
                migrations.AddIndex(
                    model_name='frame',
                    index=models.Index(Upper('target_name'), name='frames_frame_target_upper'),
                ),
            ],
        ),
    ]
