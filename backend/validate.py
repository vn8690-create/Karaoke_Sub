#!/usr/bin/env python3
"""
Quick validation script to catch common issues before deployment.

Run this before deploying to catch:
- Import errors
- Syntax errors
- Missing dependencies
- Configuration issues
"""
import sys
import importlib
import traceback
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def validate_imports():
    """Test that all modules can be imported."""
    print("🔍 Validating imports...")
    
    modules_to_test = [
        "backend.main",
        "backend.config",
        "backend.api.routes.health",
        "backend.api.routes.jobs",
        "backend.api.routes.internal",
        "backend.api.routes.file_upload",
        "backend.api.dependencies",
        "backend.services.job_manager",
        "backend.services.storage_service",
        "backend.services.firestore_service",
        "backend.services.worker_service",
        "backend.services.auth_service",
        "backend.workers.audio_worker",
        "backend.workers.lyrics_worker",
        "backend.workers.screens_worker",
        "backend.workers.video_worker",
        "backend.models.job",
        "backend.models.requests",
    ]
    
    failed = []
    
    for module_name in modules_to_test:
        try:
            importlib.import_module(module_name)
            print(f"  ✅ {module_name}")
        except Exception as e:
            print(f"  ❌ {module_name}: {e}")
            failed.append((module_name, e))
    
    if failed:
        print(f"\n❌ {len(failed)} modules failed to import:")
        for module_name, error in failed:
            print(f"\n  {module_name}:")
            print(f"    {error}")
        return False
    
    print(f"\n✅ All {len(modules_to_test)} modules imported successfully")
    return True


def validate_syntax():
    """Check for syntax errors in all Python files."""
    print("\n🔍 Checking Python syntax...")
    
    backend_dir = Path(__file__).parent
    python_files = list(backend_dir.rglob("*.py"))
    
    failed = []
    
    for py_file in python_files:
        # Skip cache and venv directories
        if any(skip in str(py_file) for skip in ["__pycache__", "venv/", ".venv/"]):
            continue
        
        try:
            with open(py_file, 'r') as f:
                compile(f.read(), str(py_file), 'exec')
        except SyntaxError as e:
            failed.append((py_file, e))
            print(f"  ❌ {py_file.relative_to(backend_dir)}: {e}")
    
    if not failed:
        print(f"  ✅ All {len(python_files)} Python files have valid syntax")
        return True
    
    print(f"\n❌ {len(failed)} files have syntax errors")
    return False


def validate_config():
    """Check that configuration can be loaded."""
    print("\n🔍 Validating configuration...")
    
    try:
        from backend.config import get_settings
        settings = get_settings()
        print(f"  ✅ Configuration loaded")
        print(f"     Environment: {settings.environment}")
        print(f"     Project: {settings.google_cloud_project or 'Not set (OK for local)'}")
        return True
    except Exception as e:
        print(f"  ❌ Configuration failed: {e}")
        traceback.print_exc()
        return False


def validate_fastapi_app():
    """Check that FastAPI app can be created."""
    print("\n🔍 Validating FastAPI application...")
    
    try:
        from backend.main import app
        print(f"  ✅ FastAPI app created successfully")
        print(f"     Title: {app.title}")
        print(f"     Version: {app.version}")
        
        # List routes
        routes = []
        for route in app.routes:
            if hasattr(route, 'methods') and hasattr(route, 'path'):
                for method in route.methods:
                    routes.append(f"{method:6s} {route.path}")
        
        print(f"     Routes: {len(routes)} endpoints")
        return True
    except Exception as e:
        print(f"  ❌ FastAPI app creation failed: {e}")
        traceback.print_exc()
        return False


def main():
    """Run all validations."""
    print("=" * 60)
    print("Backend Validation")
    print("=" * 60)
    
    results = []
    
    # Run validations
    results.append(("Syntax Check", validate_syntax()))
    results.append(("Import Check", validate_imports()))
    results.append(("Config Check", validate_config()))
    results.append(("FastAPI Check", validate_fastapi_app()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status:8s} {name}")
    
    all_passed = all(passed for _, passed in results)
    
    if all_passed:
        print("\n🎉 All validations passed! Safe to deploy.")
        return 0
    else:
        print("\n❌ Some validations failed. Fix issues before deploying.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

