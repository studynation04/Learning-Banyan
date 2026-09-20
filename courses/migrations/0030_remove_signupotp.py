from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0029_signup_otp_unique_mobile"),
    ]

    operations = [
        migrations.DeleteModel(
            name="SignupOTP",
        ),
    ]
