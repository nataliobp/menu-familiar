import ast
from pathlib import Path
from unittest import TestCase


class ArchitectureTests(TestCase):
    def test_inner_layers_do_not_import_django_or_outer_adapters(self):
        root = Path(__file__).resolve().parents[1]
        for layer in ("domain", "application"):
            for path in (root / layer).glob("*.py"):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    modules = [item.name for item in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                    for module in modules:
                        with self.subTest(path=path.name, module=module):
                            self.assertFalse(module == "django" or module.startswith(("django.", "menus.infrastructure", "menus.web")))

    def test_web_does_not_import_orm_models(self):
        root = Path(__file__).resolve().parents[1]
        for path in (root / "web").glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertNotEqual(node.module, "menus.models", path.name)
