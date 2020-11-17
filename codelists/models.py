import csv
from io import StringIO

from django.db import models
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.text import slugify

from .coding_systems import CODING_SYSTEMS


class Codelist(models.Model):
    CODING_SYSTEMS_CHOICES = sorted(
        (id, system.name) for id, system in CODING_SYSTEMS.items()
    )

    name = models.CharField(max_length=255)
    slug = models.SlugField()
    organisation = models.ForeignKey(
        "opencodelists.Organisation",
        null=True,
        related_name="codelists",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        "opencodelists.User",
        null=True,
        related_name="codelists",
        on_delete=models.CASCADE,
    )
    coding_system_id = models.CharField(
        choices=CODING_SYSTEMS_CHOICES, max_length=32, verbose_name="Coding system"
    )
    description = models.TextField()
    methodology = models.TextField()

    class Meta:
        unique_together = [("organisation", "name", "slug"), ("user", "name", "slug")]
        constraints = [
            models.CheckConstraint(
                name="%(app_label)s_%(class)s_organisation_xor_user",
                check=(
                    models.Q(organisation_id__isnull=False, user_id__isnull=True)
                    | models.Q(user_id__isnull=False, organisation_id__isnull=True)
                ),
            )
        ]

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @cached_property
    def coding_system(self):
        return CODING_SYSTEMS[self.coding_system_id]

    def get_absolute_url(self):
        return reverse("codelists:codelist", kwargs=self.url_kwargs)

    def get_update_url(self):
        return reverse("codelists:codelist-update", kwargs=self.url_kwargs)

    def get_version_create_url(self):
        return reverse("codelists:version-create", kwargs=self.url_kwargs)

    @cached_property
    def url_kwargs(self):
        return {
            "organisation_slug": self.organisation_id,
            "codelist_slug": self.slug,
        }

    def full_slug(self):
        return "{}/{}".format(self.organisation_id, self.slug)


class CodelistVersion(models.Model):
    codelist = models.ForeignKey(
        "Codelist", on_delete=models.CASCADE, related_name="versions"
    )
    version_str = models.CharField(max_length=12, verbose_name="Version")
    csv_data = models.TextField(verbose_name="CSV data", null=True)
    is_draft = models.BooleanField(default=True)

    class Meta:
        unique_together = ("codelist", "version_str")

    def save(self, *args, **kwargs):
        if self.csv_data:
            self.csv_data = self.csv_data.replace("\r\n", "\n")
        super().save(*args, **kwargs)

    @property
    def qualified_version_str(self):
        if self.is_draft:
            return f"{self.version_str}-draft"
        else:
            return self.version_str

    @property
    def organisation(self):
        return self.codelist.organisation

    def get_absolute_url(self):
        return reverse("codelists:version", kwargs=self.url_kwargs)

    def get_update_url(self):
        return reverse("codelists:version-update", kwargs=self.url_kwargs)

    def get_publish_url(self):
        return reverse("codelists:version-publish", kwargs=self.url_kwargs)

    def get_download_url(self):
        return reverse("codelists:version-download", kwargs=self.url_kwargs)

    @cached_property
    def url_kwargs(self):
        return {
            "organisation_slug": self.codelist.organisation_id,
            "codelist_slug": self.codelist.slug,
            "qualified_version_str": self.qualified_version_str,
        }

    @cached_property
    def coding_system_id(self):
        return self.codelist.coding_system_id

    @cached_property
    def coding_system(self):
        return CODING_SYSTEMS[self.coding_system_id]

    @cached_property
    def table(self):
        if self.csv_data:
            return self._old_style_table()
        else:
            return self._new_style_table()

    def _old_style_table(self):
        return list(csv.reader(StringIO(self.csv_data)))

    def _new_style_table(self):
        code_to_term = self.coding_system.code_to_term(self.codes)
        rows = [["code", "term"]]
        rows.extend([code, code_to_term.get(code, "[Unknown]")] for code in self.codes)
        return rows

    @cached_property
    def codes(self):
        if self.csv_data:
            return self._old_style_codes()
        else:
            return self._new_style_codes()

    def _old_style_codes(self):
        if self.coding_system_id in ["ctv3", "ctv3tpp", "snomedct"]:
            headers, *rows = self.table

            for header in ["CTV3ID", "CTV3Code", "ctv3_id", "snomedct_id", "id"]:
                if header in headers:
                    ix = headers.index(header)
                    break
            else:
                if self.codelist.slug == "ethnicity":
                    ix = 1
                else:
                    ix = 0

            return tuple(sorted({row[ix] for row in rows}))

    def _new_style_codes(self):
        return tuple(sorted(self.code_objs.values_list("code", flat=True)))

    def download_filename(self):
        return "{}-{}-{}".format(
            self.codelist.organisation_id, self.codelist.slug, self.version_str
        )


class DefinitionRule(models.Model):
    STATUS_CHOICES = [
        ("+", "Included with descendants"),
        ("-", "Excluded with descendants"),
    ]
    codelist = models.ForeignKey(
        "CodelistVersion", related_name="rules", on_delete=models.CASCADE
    )
    code = models.CharField(max_length=18)
    status = models.CharField(max_length=3, choices=STATUS_CHOICES, default="?")

    class Meta:
        unique_together = ("codelist", "code")


class CodeObj(models.Model):
    codelist = models.ForeignKey(
        "CodelistVersion", related_name="code_objs", on_delete=models.CASCADE
    )
    code = models.CharField(max_length=18)


class SignOff(models.Model):
    codelist = models.ForeignKey(
        "Codelist", on_delete=models.CASCADE, related_name="signoffs"
    )
    user = models.ForeignKey("opencodelists.User", on_delete=models.CASCADE)
    date = models.DateField()


class Reference(models.Model):
    codelist = models.ForeignKey(
        "Codelist", on_delete=models.CASCADE, related_name="references"
    )
    text = models.CharField(max_length=255)
    url = models.URLField()
