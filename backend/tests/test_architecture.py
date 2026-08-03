from pathlib import Path


def test_domain_layer_does_not_import_frameworks() -> None:
    domain_root = Path(__file__).parents[1] / "src" / "atlas" / "modules"
    forbidden = ("fastapi", "pydantic", "sqlalchemy", "starlette")

    for source_file in domain_root.rglob("domain/*.py"):
        source = source_file.read_text(encoding="utf-8")
        for module in forbidden:
            assert f"import {module}" not in source
            assert f"from {module}" not in source
