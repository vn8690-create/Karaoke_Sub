"""Regression tests for quote-safe Python dependency verification (no AI downloads)."""
from contextlib import redirect_stdout
from io import StringIO
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / "windows" / "verify_environment.py"
SPEC = importlib.util.spec_from_file_location("verify_environment", SCRIPT)
verify_environment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify_environment)


class WindowsPythonVerifierTests(unittest.TestCase):
    @staticmethod
    def fake_modules(cuda_available=False):
        cuda = SimpleNamespace(
            is_available=lambda: cuda_available,
            get_device_name=lambda index: "Fake NVIDIA GPU",
            get_device_properties=lambda index: SimpleNamespace(total_memory=4 * 1024**3),
        )
        torch = SimpleNamespace(__version__="2.5.1", cuda=cuda)
        return {name: torch if name == "torch" else SimpleNamespace()
                for name in verify_environment.REQUIRED_MODULES}

    def run_verify(self, modules, require_cuda=False):
        output = StringIO()

        def importer(name):
            if name not in modules:
                raise ImportError("No module named " + name)
            return modules[name]

        with patch.object(verify_environment.importlib, "import_module", side_effect=importer):
            with redirect_stdout(output):
                status = verify_environment.verify(require_cuda=require_cuda)
        return status, output.getvalue()

    def test_cpu_environment_is_valid_without_gpu(self):
        status, output = self.run_verify(self.fake_modules())
        self.assertEqual(status, 0, output)
        self.assertIn("CUDA available: False", output)
        self.assertIn("Required Python modules: OK", output)

    def test_gpu_environment_reports_cuda_and_vram(self):
        status, output = self.run_verify(self.fake_modules(cuda_available=True), require_cuda=True)
        self.assertEqual(status, 0, output)
        self.assertIn("Fake NVIDIA GPU", output)
        self.assertIn("VRAM GB: 4.0", output)

    def test_required_cuda_fails_with_clear_message(self):
        status, output = self.run_verify(self.fake_modules(), require_cuda=True)
        self.assertEqual(status, 1)
        self.assertIn("CUDA is unavailable", output)
        self.assertIn("-CpuOnly", output)

    def test_missing_ai_library_returns_clear_error_not_syntaxerror(self):
        modules = self.fake_modules()
        modules.pop("whisper_timestamped")
        status, output = self.run_verify(modules)
        self.assertEqual(status, 1)
        self.assertIn("Cannot import whisper_timestamped", output)
        self.assertNotIn("SyntaxError", output)


if __name__ == "__main__":
    unittest.main()
