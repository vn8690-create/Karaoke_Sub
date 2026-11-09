# Test Fixes Needed for Authentication

## Problem

After adding `Depends(require_auth)` to 33+ backend endpoints, all unit and integration tests are failing because they don't include authentication headers in their requests.

## Solution

All test requests to authenticated endpoints need to include:
```python
headers={"Authorization": "Bearer test-admin-token"}
```

## Files Need Updating

### 1. Global Fixture (DONE)
✅ `backend/tests/conftest.py` - Added mock_auth_service and auth_headers fixtures

### 2. Test Files to Update

Each test file needs:
1. Mock auth service in the client fixture  
2. Add `auth_headers` parameter to test methods
3. Pass `headers=auth_headers` to all client requests (get, post, put, delete)

Files:
- `backend/tests/test_jobs_api.py` - ~15 test methods  
- `backend/tests/test_upload_api.py` - ~10 test methods
- `backend/tests/test_audio_search.py` - ~5 test methods
- `backend/tests/test_api_routes.py` - ~10 test methods
- `backend/tests/test_instrumental_api.py` - ~5 test methods
- `backend/tests/emulator/test_emulator_integration.py` - ~20 test methods

## Quick Fix Script

Rather than manually updating 60+ test methods, here's a Python script to auto-fix them:

```python
#!/usr/bin/env python3
"""
Auto-fix test files to include authentication headers.
"""
import re
from pathlib import Path

def fix_test_file(filepath):
    """Add auth_headers to client requests in test file."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Pattern: client.METHOD(
    # Replace with: client.METHOD(..., headers=auth_headers)
    patterns = [
        # client.get("/path")
        (r'client\.(get|post|put|delete|patch)\((["\'][^"\']+["\'])\)', 
         r'client.\1(\2, headers=auth_headers)'),
        
        # client.get("/path", json={...})  
        (r'client\.(get|post|put|delete|patch)\((["\'][^"\']+["\']),\s*json=',
         r'client.\1(\2, headers=auth_headers, json='),
        
        # client.post("/path", data={...})
        (r'client\.(get|post|put|delete|patch)\((["\'][^"\']+["\']),\s*data=',
         r'client.\1(\2, headers=auth_headers, data='),
        
        # client.post("/path", files={...})
        (r'client\.(post)\((["\'][^"\']+["\']),\s*files=',
         r'client.\1(\2, headers=auth_headers, files='),
    ]
    
    modified = content
    for pattern, replacement in patterns:
        modified = re.sub(pattern, replacement, modified)
    
    # Add auth_headers parameter to test methods that don't have it
    # def test_something(self, client, mock_job):
    # -> def test_something(self, client, mock_job, auth_headers):
    modified = re.sub(
        r'def (test_\w+)\(self,\s*client([^)]*)\):',
        r'def \1(self, client\2, auth_headers):',
        modified
    )
    
    with open(filepath, 'w') as f:
        f.write(modified)
    
    print(f"Fixed: {filepath}")

# Find all test files
test_dir = Path("backend/tests")
for test_file in test_dir.rglob("test_*.py"):
    if 'conftest' not in str(test_file):
        fix_test_file(test_file)

print("Done!")
```

## Manual Approach

For each test method:

**Before:**
```python
def test_get_job(self, client, mock_job_manager):
    response = client.get("/api/jobs/test123")
    assert response.status_code == 200
```

**After:**
```python
def test_get_job(self, client, mock_job_manager, auth_headers):
    response = client.get("/api/jobs/test123", headers=auth_headers)
    assert response.status_code == 200
```

## Emulator Tests

Emulator tests already have `auth_headers` fixture in `backend/tests/emulator/conftest.py`.  
Just need to:
1. Add `auth_headers` parameter to test methods
2. Pass `headers=auth_headers` to client requests

## Health Endpoints

Health endpoints (`/api/health`, `/api/readiness`) should remain unauthenticated, so those tests don't need auth headers.

## Internal API Tests  

Internal API tests in `test_internal_api.py` already have auth handling via `X-Admin-Token` header. May need updating if we migrate to formal `require_admin`.

## Test Coverage

After fixes, run:
```bash
cd backend
python -m pytest tests/ -v --ignore=tests/integration
```

Should see all tests passing.

