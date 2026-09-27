from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0032_coursecontent_video_url"),
    ]

    operations = [
        migrations.AlterField(
            model_name="course",
            name="description",
            field=models.TextField(blank=True),
        ),
    ]
