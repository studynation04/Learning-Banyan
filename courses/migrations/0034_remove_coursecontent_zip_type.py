from django.db import migrations, models


def move_legacy_zip_items_to_documents(apps, schema_editor):
    CourseContent = apps.get_model("courses", "CourseContent")
    CourseContent.objects.filter(content_type="zip").update(content_type="document")


class Migration(migrations.Migration):
    dependencies = [("courses", "0033_course_description_optional")]

    operations = [
        migrations.RunPython(move_legacy_zip_items_to_documents, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="coursecontent",
            name="content_type",
            field=models.CharField(
                choices=[
                    ("folder", "Folder"),
                    ("video", "Video"),
                    ("quiz", "Online Test/Quiz"),
                    ("subjective", "Subjective Test"),
                    ("practice", "Practice Test"),
                    ("document", "Document"),
                    ("image", "Image"),
                ],
                max_length=20,
            ),
        ),
    ]
