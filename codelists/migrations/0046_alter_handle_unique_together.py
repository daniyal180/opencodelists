# Generated by Django 3.2.8 on 2021-10-26 10:07

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("opencodelists", "0007_auto_20210114_1139"),
        ("codelists", "0045_resolve_duplicate_handles"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="handle",
            unique_together={
                ("organisation", "name"),
                ("organisation", "slug"),
                ("user", "name"),
                ("user", "slug"),
            },
        ),
    ]
