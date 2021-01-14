# Generated by Django 3.1.5 on 2021-01-14 12:37

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Concept",
            fields=[
                (
                    "code",
                    models.CharField(max_length=7, primary_key=True, serialize=False),
                ),
                ("kind", models.CharField(max_length=8)),
                ("term", models.CharField(max_length=200)),
                (
                    "parent",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="children",
                        to="icd10.concept",
                    ),
                ),
            ],
        ),
    ]
