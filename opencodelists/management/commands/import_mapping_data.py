import os
from importlib import import_module
from pathlib import Path

from django.core.management import BaseCommand


def possible_modules():
    return [
        str(path.parent).replace(os.sep, ".")
        for path in Path("mappings").rglob("import_data.py")
    ]


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("dataset", choices=possible_modules())
        parser.add_argument("release_dir")

    def handle(self, dataset, release_dir, **kwargs):
        mod = import_module(dataset + ".import_data")
        fn = getattr(mod, "import_data")
        fn(release_dir)
