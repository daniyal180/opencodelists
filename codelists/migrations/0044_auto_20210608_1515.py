# Generated by Django 3.2.3 on 2021-06-08 15:15

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("codelists", "0043_auto_20210526_0952"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="reference",
            unique_together={("codelist", "url")},
        ),
        migrations.AlterUniqueTogether(
            name="signoff",
            unique_together={("codelist", "user")},
        ),
    ]
