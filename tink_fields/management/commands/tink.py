from django.core.management.base import BaseCommand, CommandError, CommandParser
from tink.proto import tink_pb2
from google.protobuf import json_format

from tink_fields.models import Keyset, Key
from tink.aead import aead_key_templates
from tink.daead import deterministic_aead_key_templates


def get_key_template_by_name(name: str) -> tink_pb2.KeyTemplate:
    template = getattr(aead_key_templates, name, None)
    if template:
        return template

    return getattr(deterministic_aead_key_templates, name)


class Command(BaseCommand):
    help = "Tink key management"

    def add_arguments(self, parser: CommandParser):
        subparsers = parser.add_subparsers(dest="subcommand", required=True)

        create_keyset = subparsers.add_parser("create-keyset", help="Create new keyset")
        create_keyset.add_argument("name", help="Key name")
        create_keyset.add_argument(
            "template",
            help="Key template (see tinkey list-key-templates)",
        )

        create_key = subparsers.add_parser(
            "create-key", help="Create a non-primary key in a keyset"
        )
        create_key.add_argument("name", help="Keyset name")
        create_key.add_argument(
            "template", help="Key template (see tinkey list-key-templates)"
        )

        promote_key = subparsers.add_parser(
            "promote-key", help="Promote key to primary in a keyset"
        )
        promote_key.add_argument("name", help="Keyset name")
        promote_key.add_argument("id", help="Key ID", type=int)

        list_keys = subparsers.add_parser("list-keys", help="List keys a keyset")
        list_keys.add_argument("name", help="Keyset name")

        delete_keyset = subparsers.add_parser(
            "delete-keyset", help="Delete keyset and all associated keys"
        )
        delete_keyset.add_argument("name", help="Keyset name")

        unsafe_export_keyset = subparsers.add_parser(
            "unsafe-export-keyset",
            help="Export keyset (INCLUDING KEY MATERIALS) as JSON",
        )
        unsafe_export_keyset.add_argument("name", help="Keyset name")

        export_keyset_info = subparsers.add_parser(
            "export-keyset-info",
            help="Export keyset info as JSON",
        )
        export_keyset_info.add_argument("name", help="Keyset name")

    def handle(self, *args, **options):
        if options["subcommand"] == "create-keyset":
            return self.create_keyset(*args, **options)
        elif options["subcommand"] == "create-key":
            return self.create_key(*args, **options)
        elif options["subcommand"] == "promote-key":
            return self.promote_key(*args, **options)
        elif options["subcommand"] == "list-keys":
            return self.list_keys(*args, **options)
        elif options["subcommand"] == "unsafe-export-keyset":
            return self.unsafe_export_keyset(*args, **options)
        elif options["subcommand"] == "export-keyset-info":
            return self.export_keyset_info(*args, **options)
        elif options["subcommand"] == "delete-keyset":
            return self.delete_keyset(*args, **options)
        else:
            raise CommandError("invalid subcommand")

    def create_keyset(self, name: str, template: str, *args, **options):
        keyset = Keyset.create(name, get_key_template_by_name(template))
        self.stdout.write(self.style.SUCCESS(f"Created keyset {keyset.id}"))

    def create_key(self, name: str, template: str, *args, **options):
        try:
            keyset = Keyset.objects.get(name=name)
        except Keyset.DoesNotExist:
            raise CommandError(f'Keyset "{name}" not found')

        key = keyset.generate_key(get_key_template_by_name(template))
        self.stdout.write(self.style.SUCCESS(f"Created key {key.id}"))

    def promote_key(self, name: str, id: int, *args, **options):
        try:
            keyset = Keyset.objects.get(name=name)
        except Keyset.DoesNotExist:
            raise CommandError(f'Keyset "{name}" not found')

        try:
            key = keyset.key_set.get(pk=id)
        except Key.DoesNotExist:
            raise CommandError(f"Key ID {id} not found in keyset")

        keyset.set_primary_key(key)
        self.stdout.write(f"Key {key.pk} promoted to primary")

    def list_keys(self, name: str, *args, **options):
        try:
            keyset = Keyset.objects.get(name=name)
            self.stdout.write(f"Key type: {keyset.type_url}")
            self.stdout.write("")
            self.stdout.write("ID\tPrimary\tStatus\tPrefix")
            for key in keyset.key_set.all():
                self.stdout.write(
                    f"{key.id}\t{'Y' if key.is_primary else 'N'}\t{tink_pb2.KeyStatusType.Name(key.status)}\t{tink_pb2.OutputPrefixType.Name(key.output_prefix_type)}"
                )
        except Keyset.DoesNotExist:
            raise CommandError(f'Keyset "{name}" not found')

    def delete_keyset(self, name: str, *args, **options):
        try:
            keyset = Keyset.objects.get(name=name)
            keyset.delete()
            self.stdout.write(self.style.SUCCESS(f'Deleted keyset "{name}"'))
        except Keyset.DoesNotExist:
            raise CommandError(f'Keyset "{name}" not found')

    def unsafe_export_keyset(self, name: str, *args, **options):
        try:
            keyset = Keyset.objects.get(name=name)
            self.stdout.write(json_format.MessageToJson(keyset.export_keyset()))
        except Keyset.DoesNotExist:
            raise CommandError(f'Keyset "{name}" not found')

    def export_keyset_info(self, name: str, *args, **options):
        try:
            keyset = Keyset.objects.get(name=name)
            self.stdout.write(json_format.MessageToJson(keyset.export_keyset_info()))
        except Keyset.DoesNotExist:
            raise CommandError(f'Keyset "{name}" not found')
