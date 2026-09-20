# Option/answer fields as TEXT so MySQL/MariaDB utf8mb4 stays under the
# 65535-byte InnoDB row limit (VARCHAR(5000) x 5 overflows).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0015_discussion_reply_updated_at"),
    ]

    operations = [
        migrations.AlterField(
            model_name="question",
            name="option_a",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="question",
            name="option_b",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="question",
            name="option_c",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="question",
            name="option_d",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="question",
            name="correct_answer",
            field=models.TextField(
                blank=True,
                help_text="For choice: A/B/C/D or A,B for multiple",
            ),
        ),
    ]
