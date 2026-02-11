from datetime import datetime, timedelta
import hashlib

from django.db import migrations, models
from django.utils import timezone


def populate_media_created_at(apps, schema_editor):
    Team5Media = apps.get_model("team5", "Team5Media")
    tz = timezone.get_current_timezone()
    base = timezone.make_aware(datetime(2024, 1, 1, 12, 0, 0), tz)

    special_dates = {
        "occasion-22bahman-": datetime(2026, 2, 11, 12, 0, 0),
        "occasion-nowruz-": datetime(2026, 3, 21, 12, 0, 0),
        "occasion-yalda-": datetime(2025, 12, 21, 12, 0, 0),
        "occasion-christmas-": datetime(2025, 12, 25, 20, 0, 0),
        "occasion-imammahdi-": datetime(2026, 2, 15, 20, 0, 0),
        "occasion-chaharshanbe-soori-": datetime(2026, 3, 18, 20, 0, 0),
    }

    for media in Team5Media.objects.all().only("media_id"):
        media_id = str(media.media_id)
        matched = None
        for prefix, dt in special_dates.items():
            if media_id.startswith(prefix):
                matched = timezone.make_aware(dt, tz)
                break
        if matched is None:
            digest = hashlib.md5(media_id.encode("utf-8")).hexdigest()
            offset = int(digest[:6], 16) % 700
            matched = base + timedelta(days=offset)
        Team5Media.objects.filter(media_id=media_id).update(created_at=matched)


class Migration(migrations.Migration):
    dependencies = [
        ("team5", "0004_team5media_author_and_image_fields"),
        ("team5", "0004_rename_team5_team5c_city_na_f57158_idx_team5_team5_city_na_2559f4_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="team5media",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, db_index=True, default=timezone.now),
            preserve_default=False,
        ),
        migrations.RunPython(populate_media_created_at, migrations.RunPython.noop),
    ]
