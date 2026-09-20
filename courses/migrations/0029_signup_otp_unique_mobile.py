from django.db import migrations, models


def empty_mobile_to_null(apps, schema_editor):
    StudentProfile = apps.get_model("courses", "StudentProfile")
    StudentProfile.objects.filter(mobile_number="").update(mobile_number=None)


def null_mobile_to_empty(apps, schema_editor):
    StudentProfile = apps.get_model("courses", "StudentProfile")
    StudentProfile.objects.filter(mobile_number__isnull=True).update(mobile_number="")


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0028_studentprofile_mobile_number"),
    ]

    operations = [
        migrations.AlterField(
            model_name="studentprofile",
            name="mobile_number",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Required at registration. Must be unique. Existing accounts may be empty.",
                max_length=20,
                null=True,
            ),
        ),
        migrations.RunPython(empty_mobile_to_null, null_mobile_to_empty),
        migrations.AlterField(
            model_name="studentprofile",
            name="mobile_number",
            field=models.CharField(
                blank=True,
                help_text="Required at registration. Must be unique. Existing accounts may be empty.",
                max_length=20,
                null=True,
                unique=True,
            ),
        ),
        migrations.CreateModel(
            name="SignupOTP",
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
                ("mobile_number", models.CharField(max_length=20, unique=True)),
                ("username", models.CharField(max_length=150)),
                ("email", models.EmailField(max_length=254)),
                ("first_name", models.CharField(max_length=150)),
                ("last_name", models.CharField(blank=True, max_length=150)),
                ("password", models.CharField(max_length=128)),
                ("otp_hash", models.CharField(max_length=64)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("last_sent_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Signup OTP",
                "verbose_name_plural": "Signup OTPs",
                "ordering": ["-created_at"],
            },
        ),
    ]
