# Generated by Django 3.1.1 on 2020-10-08 09:41

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("codelists", "0010_auto_20201008_0912"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="codelist",
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name="codelist",
            name="name",
        ),
        migrations.RemoveField(
            model_name="codelist",
            name="project",
        ),
        migrations.RemoveField(
            model_name="codelist",
            name="slug",
        ),
    ]
