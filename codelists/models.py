from django.db import models
from django.urls import reverse
from django.utils.functional import cached_property

from mappings.bnfdmd.mappers import bnf_to_dmd
from opencodelists.csv_utils import (
    csv_data_to_rows,
    dict_rows_to_csv_data,
    rows_to_csv_data,
)
from opencodelists.hash_utils import hash, unhash

from .codeset import Codeset
from .coding_systems import CODING_SYSTEMS
from .hierarchy import Hierarchy
from .presenters import present_definition_for_download


class Codelist(models.Model):
    CODING_SYSTEMS_CHOICES = sorted(
        (id, system.name) for id, system in CODING_SYSTEMS.items()
    )

    coding_system_id = models.CharField(
        choices=CODING_SYSTEMS_CHOICES, max_length=32, verbose_name="Coding system"
    )
    description = models.TextField(null=True, blank=True)
    methodology = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @cached_property
    def coding_system(self):
        return CODING_SYSTEMS[self.coding_system_id]

    @property
    def codelist_type(self):
        if self.user_id:
            assert not self.organisation_id
            return "user"
        else:
            assert self.organisation_id
            return "organisation"

    @cached_property
    def current_handle(self):
        return self.handles.filter(is_current=True).get()

    @property
    def name(self):
        return self.current_handle.name

    @property
    def slug(self):
        return self.current_handle.slug

    @property
    def user_id(self):
        return self.current_handle.user_id

    @property
    def user(self):
        return self.current_handle.user

    @property
    def organisation_id(self):
        return self.current_handle.organisation_id

    @property
    def organisation(self):
        return self.current_handle.organisation

    def get_absolute_url(self):
        return reverse(
            f"codelists:{self.codelist_type}_codelist", kwargs=self.url_kwargs
        )

    def get_update_url(self):
        return reverse(
            f"codelists:{self.codelist_type}_codelist_update", kwargs=self.url_kwargs
        )

    def get_version_upload_url(self):
        return reverse(
            f"codelists:{self.codelist_type}_version_upload", kwargs=self.url_kwargs
        )

    def get_versions_api_url(self):
        return reverse(
            f"codelists_api:{self.codelist_type}_versions", kwargs=self.url_kwargs
        )

    @property
    def url_kwargs(self):
        if self.codelist_type == "organisation":
            return {
                "organisation_slug": self.organisation_id,
                "codelist_slug": self.slug,
            }
        else:
            return {
                "username": self.user_id,
                "codelist_slug": self.slug,
            }

    def full_slug(self):
        if self.codelist_type == "organisation":
            return "{}/{}".format(self.organisation_id, self.slug)
        else:
            return "user/{}/{}".format(self.user_id, self.slug)

    def is_new_style(self):
        return self.versions.filter(csv_data__isnull=True).exists()

    def can_be_edited_by(self, user):
        """Return whether codelist can be edited by given user.

        A codelist can be edited by a user if:

            * the user is authenticated
            * the user is a collaborator on the codelist
            * the codelist is owned by the user
            * the codelist is owned by one of the organisations the user is a member of
        """

        if not user.is_authenticated:
            return False

        if self.collaborations.filter(collaborator=user).exists():
            return True

        if self.codelist_type == "user":
            return user == self.user
        else:
            return user.is_member(self.organisation)

    def visible_versions(self, user):
        """Return all versions visible to the user, with newest first."""

        versions = self.versions.order_by("-id")
        if not self.can_be_edited_by(user):
            versions = versions.filter(status=Status.PUBLISHED)

        return versions

    def latest_visible_version(self, user):
        """Return latest version visible to the user, or None if no such version
        exists."""

        return self.visible_versions(user).first()


class Handle(models.Model):
    codelist = models.ForeignKey(
        "Codelist", on_delete=models.CASCADE, related_name="handles"
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField()
    organisation = models.ForeignKey(
        "opencodelists.Organisation",
        null=True,
        related_name="handles",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        "opencodelists.User",
        null=True,
        related_name="handles",
        on_delete=models.CASCADE,
    )
    is_current = models.BooleanField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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


class Status(models.TextChoices):
    DRAFT = "draft"  # the version is being edited in the builder
    UNDER_REVIEW = "under review"  # the version is being reviewed
    PUBLISHED = "published"  # the version has been published and cannot be deleted


class CodelistVersion(models.Model):
    codelist = models.ForeignKey(
        "Codelist", on_delete=models.CASCADE, related_name="versions"
    )

    status = models.CharField(max_length=len("under review"), choices=Status.choices)

    # If set, indicates that a CodelistVersion is a draft that's being edited in the
    # builder.
    draft_owner = models.ForeignKey(
        "opencodelists.User", related_name="drafts", on_delete=models.CASCADE, null=True
    )
    tag = models.CharField(max_length=12, null=True)
    csv_data = models.TextField(verbose_name="CSV data", null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("codelist", "tag")

    class Manager(models.Manager):
        def get_by_hash(self, hash):
            """Return the CodelistVersion with given hash."""
            id = unhash(hash, "CodelistVersion")
            return self.get(id=id)

    objects = Manager()

    def save(self, *args, **kwargs):
        if self.csv_data:
            self.csv_data = self.csv_data.replace("\r\n", "\n")
        super().save(*args, **kwargs)

    @property
    def organisation(self):
        return self.codelist.organisation

    @property
    def user(self):
        return self.codelist.user

    def get_absolute_url(self):
        return reverse(
            f"codelists:{self.codelist_type}_version", kwargs=self.url_kwargs
        )

    def get_publish_url(self):
        return reverse(
            f"codelists:{self.codelist_type}_version_publish", kwargs=self.url_kwargs
        )

    def get_download_url(self):
        return reverse(
            f"codelists:{self.codelist_type}_version_download", kwargs=self.url_kwargs
        )

    def get_download_definition_url(self):
        return reverse(
            f"codelists:{self.codelist_type}_version_download_definition",
            kwargs=self.url_kwargs,
        )

    def get_dmd_download_url(self):
        return reverse(
            f"codelists:{self.codelist_type}_version_dmd_download",
            kwargs=self.url_kwargs,
        )

    def get_create_url(self):
        return reverse(
            f"codelists:{self.codelist_type}_version_create", kwargs=self.url_kwargs
        )

    def get_builder_url(self, view_name, *args):
        return reverse(f"builder:{view_name}", args=[self.hash] + list(args))

    def get_diff_url(self, other_clv):
        kwargs = self.url_kwargs
        kwargs["other_tag_or_hash"] = other_clv.tag_or_hash
        return reverse(f"codelists:{self.codelist_type}_version_diff", kwargs=kwargs)

    @property
    def url_kwargs(self):
        kwargs = self.codelist.url_kwargs
        kwargs["tag_or_hash"] = self.tag_or_hash
        return kwargs

    @property
    def hash(self):
        return hash(self.id, "CodelistVersion")

    @property
    def tag_or_hash(self):
        return self.tag or self.hash

    @cached_property
    def coding_system_id(self):
        return self.codelist.coding_system_id

    @cached_property
    def coding_system(self):
        return CODING_SYSTEMS[self.coding_system_id]

    @property
    def codelist_type(self):
        return self.codelist.codelist_type

    def full_slug(self):
        return f"{self.codelist.full_slug()}/{self.tag_or_hash}"

    @property
    def codeset(self):
        """Return Codeset for the codes related to this CodelistVersion."""

        if self.csv_data:
            return self._old_style_codeset()
        else:
            return self._new_style_codeset()

    def _old_style_codeset(self):
        if not hasattr(self.coding_system, "ancestor_relationships"):
            # If coding system does not define relationships, then we cannot build a
            # hierarchy, and so it's not clear what a codeset is for.
            return

        hierarchy = Hierarchy.from_codes(self.coding_system, self.codes)
        return Codeset.from_codes(set(self.codes), hierarchy)

    def _new_style_codeset(self):
        code_to_status = dict(self.code_objs.values_list("code", "status"))
        hierarchy = Hierarchy.from_codes(self.coding_system, list(code_to_status))
        return Codeset(code_to_status, hierarchy)

    @property
    def table(self):
        if self.csv_data:
            return self._old_style_table()
        else:
            return self._new_style_table()

    def _old_style_table(self):
        return csv_data_to_rows(self.csv_data)

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
        if self.coding_system_id in ["ctv3", "icd10", "snomedct"]:
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
        return tuple(sorted(self.codeset.codes()))

    def csv_data_for_download(self):
        if self.csv_data:
            return self.csv_data
        return rows_to_csv_data(self.table)

    def definition_csv_data_for_download(self):
        return rows_to_csv_data(present_definition_for_download(self))

    def dmd_csv_data_for_download(self):
        assert self.coding_system_id == "bnf"
        headers = ["dmd_type", "dmd_id", "dmd_name", "bnf_code"]
        return dict_rows_to_csv_data(headers, bnf_to_dmd(self.codes))

    def download_filename(self):
        if self.codelist_type == "user":
            return "{}-{}-{}".format(
                self.codelist.user_id, self.codelist.slug, self.tag_or_hash
            )
        else:
            return "{}-{}-{}".format(
                self.codelist.organisation_id, self.codelist.slug, self.tag_or_hash
            )

    @property
    def is_draft(self):
        return self.status == Status.DRAFT

    @property
    def is_under_review(self):
        return self.status == Status.UNDER_REVIEW

    @property
    def is_published(self):
        return self.status == Status.PUBLISHED


class CodeObj(models.Model):
    STATUS_CHOICES = [
        ("?", "Undecided"),
        ("!", "In conflict"),
        ("+", "Included with descendants"),
        ("(+)", "Included by ancestor"),
        ("-", "Excluded with descendants"),
        ("(-)", "Excluded by ancestor"),
    ]
    version = models.ForeignKey(
        "CodelistVersion", related_name="code_objs", on_delete=models.CASCADE
    )
    code = models.CharField(max_length=18)
    status = models.CharField(max_length=3, choices=STATUS_CHOICES, default="?")

    class Meta:
        unique_together = ("version", "code")

    def is_included(self):
        return self.status in ["+", "(+)"]

    def is_excluded(self):
        return self.status in ["-", "(-)"]


class Search(models.Model):
    version = models.ForeignKey(
        "CodelistVersion", related_name="searches", on_delete=models.CASCADE
    )
    term = models.CharField(max_length=255, null=True)
    code = models.CharField(max_length=18, null=True)
    slug = models.SlugField()

    class Meta:
        unique_together = ("version", "slug")
        constraints = [
            models.CheckConstraint(
                name="%(app_label)s_%(class)s_term_xor_code",
                check=(
                    models.Q(term__isnull=False, code__isnull=True)
                    | models.Q(code__isnull=False, term__isnull=True)
                ),
            )
        ]

    @property
    def term_or_code(self):
        return self.term or f"code: {self.code}"


class SearchResult(models.Model):
    search = models.ForeignKey(
        "Search", related_name="results", on_delete=models.CASCADE
    )
    code_obj = models.ForeignKey(
        "CodeObj", related_name="results", on_delete=models.CASCADE
    )

    class Meta:
        unique_together = ("search", "code_obj")


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
    url = models.URLField(max_length=1000)


class Collaboration(models.Model):
    codelist = models.ForeignKey(
        "Codelist", on_delete=models.CASCADE, related_name="collaborations"
    )
    collaborator = models.ForeignKey(
        "opencodelists.User", on_delete=models.CASCADE, related_name="collaborations"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
