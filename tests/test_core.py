import unittest
from unittest.mock import MagicMock, patch
from env_snapshot.core import classify_dependencies, resolve_torch_url
from env_snapshot.models import Snapshot

class TestCore(unittest.TestCase):
    
    def test_resolve_torch_url(self):
        # Case 1: CUDA 118
        installed = [{"name": "torch", "version": "2.0.1+cu118"}]
        url = resolve_torch_url(installed)
        self.assertEqual(url, "https://download.pytorch.org/whl/cu118")
        
        # Case 2: CPU
        installed = [{"name": "torch", "version": "2.0.1+cpu"}]
        url = resolve_torch_url(installed)
        self.assertEqual(url, "https://download.pytorch.org/whl/cpu")
        
        # Case 3: No local ID
        installed = [{"name": "torch", "version": "2.0.1"}]
        url = resolve_torch_url(installed)
        self.assertIsNone(url)
        
        # Case 4: Not installed
        url = resolve_torch_url([])
        self.assertIsNone(url)

    def test_classify_dependencies_with_groups(self):
        installed = [
            {"name": "torch", "version": "2.0.1+cu118"},
            {"name": "numpy", "version": "1.24.0"},
            {"name": "requests", "version": "2.31.0"},
            {"name": "my-local-pkg", "version": "0.1.0", "editable": True},
        ]
        
        root_names = {"torch", "numpy", "requests", "my-local-pkg"}
        req_names = {"numpy"} # numpy in reqs -> dependencies
        
        # Base has torch in 'gpu' group
        base_dep_map = {"torch": "gpu"}
        base_toml = {
            "project": {"name": "test-proj", "version": "0.1"},
            "tool": {"uv": {"index": [{"name": "pytorch-cuda", "url": "placeholder"}]}}
        }
        
        snapshot = classify_dependencies(installed, root_names, req_names, base_dep_map, base_toml)
        
        # Check Torch is in Optional 'gpu'
        self.assertNotIn("torch==2.0.1+cu118", snapshot.dependencies)
        self.assertIn("gpu", snapshot.optional_dependencies)
        self.assertIn("torch==2.0.1+cu118", snapshot.optional_dependencies["gpu"])
        
        # Check Numpy: Is in req_names -> dependencies list
        self.assertIn("numpy", snapshot.dependencies)
        # Should NOT be in user-downloaded even if it is a root
        self.assertNotIn("numpy", snapshot.user_downloaded)
        
        # Requests (root, not in base, not in reqs) -> user-downloaded
        self.assertIn("requests", snapshot.user_downloaded)
        
        # Check user-compiled (editable)
        self.assertEqual(len(snapshot.user_compiled), 1)
        self.assertIn("my-local-pkg (editable/local)", snapshot.user_compiled)

    def test_classify_dependencies_main_group(self):
        installed = [{"name": "flask", "version": "3.0.0"}]
        root_names = {"flask"}
        req_names = set()
        base_dep_map = {"flask": "main"}
        base_toml = {}
        
        snapshot = classify_dependencies(installed, root_names, req_names, base_dep_map, base_toml)
        
        self.assertIn("flask==3.0.0", snapshot.dependencies)
        self.assertEqual(len(snapshot.user_downloaded), 0)

if __name__ == "__main__":
    unittest.main()
