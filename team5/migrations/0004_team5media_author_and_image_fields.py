from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("team5", "0003_team5recommendationfeedback"),
    ]

    operations = [
        migrations.AddField(
            model_name="team5media",
            name="author_display_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="team5media",
            name="author_user_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="team5media",
            name="media_image_url",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
    ]
