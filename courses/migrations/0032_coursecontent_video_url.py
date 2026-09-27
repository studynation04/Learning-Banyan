from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0031_course_content_and_exam_hint"),
    ]

    operations = [
        migrations.AddField(
            model_name="coursecontent",
            name="video_url",
            field=models.CharField(
                blank=True,
                default="",
                help_text="YouTube link when the video is not an uploaded file.",
                max_length=500,
            ),
        ),
    ]
