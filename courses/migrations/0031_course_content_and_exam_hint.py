from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0030_remove_signupotp"),
    ]

    operations = [
        migrations.AddField(
            model_name="course",
            name="discount",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Rupee amount taken off the price.",
                max_digits=10,
            ),
        ),
        migrations.AddField(
            model_name="course",
            name="expires_on",
            field=models.DateField(
                blank=True,
                help_text="Leave empty for lifetime access.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="course",
            name="price",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Course price in rupees. 0 means free.",
                max_digits=10,
            ),
        ),
        migrations.AddField(
            model_name="course",
            name="subcategory",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Optional sub category, e.g. CUET.",
                max_length=150,
            ),
        ),
        migrations.AddField(
            model_name="exam",
            name="allow_hint",
            field=models.BooleanField(
                default=False,
                help_text="If enabled, students can open each question's hint during practice.",
            ),
        ),
        migrations.AlterField(
            model_name="studentprofile",
            name="mobile_number",
            field=models.CharField(
                blank=True,
                help_text="Optional. Must be unique when a number is provided.",
                max_length=20,
                null=True,
                unique=True,
            ),
        ),
        migrations.CreateModel(
            name="CourseContent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "content_type",
                    models.CharField(
                        choices=[
                            ("folder", "Folder"),
                            ("video", "Video"),
                            ("quiz", "Online Test/Quiz"),
                            ("subjective", "Subjective Test"),
                            ("practice", "Practice Test"),
                            ("document", "Document"),
                            ("image", "Image"),
                            ("zip", "Zip File"),
                        ],
                        max_length=20,
                    ),
                ),
                ("title", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True, default="")),
                (
                    "file",
                    models.FileField(
                        blank=True, null=True, upload_to="course_content/"
                    ),
                ),
                ("order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="contents",
                        to="courses.course",
                    ),
                ),
                (
                    "exam",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="course_contents",
                        to="courses.exam",
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.CASCADE,
                        related_name="children",
                        to="courses.coursecontent",
                    ),
                ),
            ],
            options={
                "ordering": ["order", "id"],
            },
        ),
    ]
