import argparse
import sys
from datetime import datetime
from importlib import import_module

from django.core.management import BaseCommand

from codelists.coding_systems import CODING_SYSTEMS
from coding_systems.versioning.models import CodingSystemRelease


def date_yymmdd(input_date):
    try:
        return datetime.strptime(input_date, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"Not a valid date (YYYY-MM-DD): {input_date}")


def coding_system_choices():
    def has_import_data(coding_system_id):
        try:
            import_module(f"coding_systems.{coding_system_id}.import_data")
            return True
        except ModuleNotFoundError:
            return False

    return [
        coding_system
        for coding_system in CODING_SYSTEMS.keys()
        if has_import_data(coding_system)
    ]


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "coding_system_id", help="Coding system id", choices=coding_system_choices()
        )
        parser.add_argument("release_dir", help="Path to release directory or file")
        parser.add_argument(
            "--release", dest="release_name", help="Release name", required=True
        )
        parser.add_argument(
            "--valid-from",
            type=date_yymmdd,
            help="For coding system imports: date the release is valid from, in YYYY-MM-DD format",
            required=True,
        )
        parser.add_argument(
            "--import-ref",
            help="For coding system imports: optional reference for this import",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force an overwrite of a coding system release",
        )
        parser.add_argument(
            "--skip-compatibility-check",
            action="store_true",
            help="Skip checking compatibility of existing codelist versions",
        )
        parser.add_argument(
            "--latest",
            action="store_true",
            help="Download only if is the latest release (dmd and snomedct only)",
            default=False,
        )

    def handle(
        self,
        coding_system_id,
        release_dir,
        release_name,
        valid_from,
        import_ref,
        force,
        skip_compatibility_check,
        latest,
        **kwargs,
    ):
        if latest:
            if coding_system_id not in ["dmd", "snomedct"]:
                raise ValueError("--latest is only available for dmd imports")

        if (
            CodingSystemRelease.objects.filter(
                coding_system=coding_system_id,
                release_name=release_name,
                valid_from=valid_from,
            ).exists()
            and not force
        ):
            self.stdout.write(
                f"A coding system release already exists for {coding_system_id} with release '{release_name}' and "
                f"valid from date {valid_from.strftime('%Y%m%d')}. Use the --force option to overwrite "
                "an existing release"
            )
            sys.exit(1)

        mod = import_module(f"coding_systems.{coding_system_id}.import_data")
        fn = getattr(mod, "import_data")
        import_kwargs = dict(
            release_name=release_name,
            valid_from=valid_from,
            import_ref=import_ref,
            check_compatibility=not skip_compatibility_check,
        )
        if latest:
            import_kwargs["latest"] = latest

        fn(release_dir, **import_kwargs)
        self.stdout.write(
            "\n*** APP RESTART REQUIRED ***\n"
            "Import complete; run `dokku ps:restart opencodelists` to restart the app"
        )
