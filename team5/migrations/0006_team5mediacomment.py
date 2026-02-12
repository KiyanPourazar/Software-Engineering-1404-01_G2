from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("team5", "0005_team5media_created_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="Team5MediaComment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("user_id", models.UUIDField(db_index=True)),
                ("user_email", models.EmailField(blank=True, default="", max_length=254)),
                ("media_id", models.CharField(db_index=True, max_length=128)),
                ("body", models.TextField()),
                ("sentiment_score", models.FloatField(default=0.0)),
                (
                    "sentiment_label",
                    models.CharField(
                        choices=[("positive", "positive"), ("negative", "negative"), ("neutral", "neutral")],
                        db_index=True,
                        default="neutral",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "indexes": [
                    models.Index(fields=["media_id", "sentiment_label"], name="team5_team5_media_i_8bbf81_idx"),
                    models.Index(fields=["user_id", "sentiment_label"], name="team5_team5_user_id_efafe5_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("user_id", "media_id"),
                        name="team5_unique_user_media_comment",
                    )
                ],
            },
        ),
    ]
