import json
from pathlib import Path
import tempfile
import unittest
from build_release import cached_engine, digest, engine_key


class BuildCacheTests(unittest.TestCase):
    def test_reuse_requires_matching_source_and_archive_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            spec = {"repository": "repo", "revision": "a" * 40}
            self.assertIsNone(cached_engine(root, spec))
            archive = root / "engine.zip"
            archive.write_bytes(b"verified engine")
            (root / "engine.json").write_text(
                json.dumps({"key": engine_key(spec), "sha256": digest(archive)})
            )
            self.assertEqual(cached_engine(root, spec), archive)
            with self.assertRaises(ValueError):
                cached_engine(root, dict(spec, revision="b" * 40))
            archive.write_bytes(b"corrupted download")
            with self.assertRaises(ValueError):
                cached_engine(root, spec)


class PackageContentsTests(unittest.TestCase):
    def test_runtime_allowlist_includes_local_import_dependencies(self):
        import ast
        from package import ROOT, RUNTIME_MODULES

        runtime = set(RUNTIME_MODULES)
        for name in runtime:
            source = ast.parse((ROOT / name).read_text(encoding="utf8"))
            for node in ast.walk(source):
                imports = (
                    [node.module]
                    if isinstance(node, ast.ImportFrom)
                    else [item.name for item in node.names]
                    if isinstance(node, ast.Import)
                    else []
                )
                for module in imports:
                    if module and (ROOT / (module + ".py")).is_file():
                        self.assertIn(module + ".py", runtime, f"{name} needs {module}")
