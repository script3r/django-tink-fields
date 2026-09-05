"""Run with `python -m benchmarks.keyset_cache` from the repository root."""

from pathlib import Path
from statistics import median
from timeit import repeat

from django.conf import settings

from tink_fields.fields import KeysetManager


def main() -> None:
    settings.configure(
        TINK_FIELDS_CONFIG={
            "default": {
                "path": Path(__file__).resolve().parents[1] / "tink_fields/test/test_plaintext_keyset.json",
                "cleartext": True,
            }
        }
    )

    def initialize_fields() -> None:
        KeysetManager.clear_cache()
        managers = [KeysetManager("default") for _ in range(100)]
        for manager in managers:
            _ = manager.aead_primitive

    cold = median(repeat(initialize_fields, number=20, repeat=7)) / 20
    manager = KeysetManager("default")
    _ = manager.aead_primitive
    warm = median(repeat(lambda: manager.aead_primitive.encrypt(b"secret", b""), number=100_000, repeat=7)) / 100_000
    print(f"Initialize 100 fields sharing a keyset: {cold * 1_000:.3f} ms")
    print(f"Warm primitive access and encryption: {warm * 1_000_000:.3f} us")


if __name__ == "__main__":
    main()
