# Phase 6: Secrets Management - Research

**Researched:** 2026-04-09
**Domain:** Streamlit secrets management, gspread authentication, credential migration
**Confidence:** HIGH

## Summary

Phase 6 replaces the current `oauth2client`-based Google Sheets authentication with Streamlit's native `st.secrets` system and `gspread.service_account_from_dict()`. This is a straightforward credential migration — the app already has demo-mode detection and graceful degradation, so the change is mostly mechanical.

**Primary recommendation:** Replace `credentials.json` file reads with `st.secrets["google_credentials"]` dict access, use `gspread.service_account_from_dict()` directly, and detect missing secrets via `try/except StreamlitSecretNotFoundError`.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `gspread` | >=6.0 (latest: 6.2.1) | Google Sheets API client | Already in use; `service_account_from_dict()` is the canonical auth method |
| `streamlit` | >=1.45 (installed: 1.53.0) | App framework + secrets management | Native `st.secrets` is the built-in solution for local secrets |
| `google-auth` | (transitive via gspread) | OAuth2 credentials handling | gspread uses this internally — no direct dependency needed |

### No New Dependencies
This phase **removes** a dependency (`oauth2client`) and requires no new ones. The `google-auth` library is already installed as a transitive dependency of `gspread`.

### Removed
| Library | Reason |
|---------|--------|
| `oauth2client` | Deprecated since 2018. `gspread>=6.0` uses `google.oauth2.service_account` internally |

## Architecture Patterns

### Pattern 1: Centralized Credential Detection in config.py
**What:** Add a helper function `get_google_credentials()` in `config.py` (or a new `auth/credentials.py`) that wraps `st.secrets` access with proper error handling.
**When to use:** This is the single point of truth for "are credentials available?"
**Example:**
```python
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError
from typing import Optional, Dict

def get_google_credentials() -> Optional[Dict]:
    try:
        creds = dict(st.secrets["google_credentials"])
        if creds.get("type") == "service_account" and creds.get("private_key"):
            return creds
    except (StreamlitSecretNotFoundError, KeyError, TypeError):
        pass
    return None

def has_google_credentials() -> bool:
    return get_google_credentials() is not None
```

### Pattern 2: secrets.toml with TOML Section
**What:** Store the full Google service account JSON as a TOML section in `.streamlit/secrets.toml`
**When to use:** Single-credential apps like this one
**Example:**
```toml
# .streamlit/secrets.toml
[google_credentials]
type = "service_account"
project_id = "your-project-id"
private_key_id = "your-key-id"
private_key = "-----BEGIN PRIVATE KEY-----\nMIIEvQ...\n-----END PRIVATE KEY-----\n"
client_email = "your-sa@your-project.iam.gserviceaccount.com"
client_id = "123456789"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/..."
```

### Pattern 3: Graceful Secret Access
**What:** Always wrap `st.secrets` access in `try/except` — even `.get()` and `in` operator raise exceptions when no secrets file exists.
**When to use:** Every access to `st.secrets` anywhere in the codebase
**Example:**
```python
# WARNING: Even st.secrets.get() raises StreamlitSecretNotFoundError
# when NO secrets.toml file exists at all. Must use try/except.
from streamlit.errors import StreamlitSecretNotFoundError

try:
    creds = st.secrets["google_credentials"]
except (StreamlitSecretNotFoundError, KeyError):
    creds = None
```

### Anti-Patterns to Avoid
- **Checking `os.path.exists(".streamlit/secrets.toml")`**: Fragile, doesn't account for global secrets file at `~/.streamlit/secrets.toml`. Use `st.secrets` with try/except instead.
- **Using `st.secrets.get()` without try/except**: Raises `StreamlitSecretNotFoundError` when no file exists — `.get()` is NOT safe.
- **Using `'key' in st.secrets` without try/except**: Same issue — raises exception when no file exists.
- **Storing private_key as multi-line TOML**: Use `\n` escape sequences in a basic TOML string (double quotes), not literal newlines in a multi-line string.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Credential loading | Custom file reader | `st.secrets` | Handles global + project files, TOML parsing, env var exposure |
| OAuth2 credentials | Manual token management | `gspread.service_account_from_dict()` | Handles refresh, scopes, and auth internally |
| Demo mode detection | File existence checks | `try/except StreamlitSecretNotFoundError` | Covers both missing file AND missing key |

## Common Pitfalls

### Pitfall 1: st.secrets.get() Is NOT Safe
**What goes wrong:** Using `st.secrets.get("key", default)` assuming it returns `default` when no secrets file exists.
**Why it happens:** `st.secrets.get()` delegates to `__getitem__` which calls `_parse()` which raises `StreamlitSecretNotFoundError` when no secrets file is found.
**How to avoid:** Always wrap any `st.secrets` access in `try/except (StreamlitSecretNotFoundError, KeyError)`.
**Warning signs:** App crashes on first launch for new developers.

### Pitfall 2: Private Key Newlines in TOML
**What goes wrong:** The `private_key` field contains `\n` characters that must be preserved. If TOML parsing strips or mangles them, authentication fails.
**Why it happens:** Confusion between TOML literal strings (single quotes, no escape processing) and basic strings (double quotes, `\n` is processed as newline).
**How to avoid:** Use double-quoted TOML strings with `\n` — TOML will correctly parse these as newline characters. The key value should look like `"-----BEGIN PRIVATE KEY-----\nMIIE...\n-----END PRIVATE KEY-----\n"`.
**Warning signs:** `google.auth.exceptions.MalformedError` or "Could not parse the private key" errors.

### Pitfall 3: dict() Conversion for Nested TOML Sections
**What goes wrong:** `st.secrets["google_credentials"]` returns a `Secrets` proxy object, not a plain dict. Some libraries may not handle this.
**Why it happens:** Streamlit's secrets implementation uses a custom mapping type.
**How to avoid:** Wrap with `dict(st.secrets["google_credentials"])` before passing to `gspread.service_account_from_dict()`.
**Warning signs:** TypeError or unexpected behavior when gspread tries to access credential fields.

### Pitfall 4: Forgetting to Remove CREDENTIALS_FILE from config.py
**What goes wrong:** Dead import `from config import CREDENTIALS_FILE` causes lint errors or confusion.
**Why it happens:** config.py defines `CREDENTIALS_FILE = "credentials.json"` and google_sheets.py imports it.
**How to avoid:** Remove the constant from config.py and the import from google_sheets.py in the same task.
**Warning signs:** `ImportError` or unused import warnings.

### Pitfall 5: Scope Mismatch
**What goes wrong:** Current code uses `["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]` (old scopes). `gspread.service_account_from_dict()` defaults to `["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]`.
**Why it happens:** The old `spreadsheets.google.com/feeds` scope was from the older Sheets API v3.
**How to avoid:** Don't pass custom scopes — let `service_account_from_dict()` use its defaults, which are correct for Sheets API v4.
**Warning signs:** Authentication works but API calls fail with permission errors.

## Code Examples

### Rewrite: auth/google_sheets.py get_client()
```python
# BEFORE (current code):
from oauth2client.service_account import ServiceAccountCredentials
from config import CREDENTIALS_FILE

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

def get_client() -> gspread.Client:
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        CREDENTIALS_FILE, SCOPES
    )
    return gspread.authorize(creds)

# AFTER (new code):
import gspread
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

def get_client() -> gspread.Client:
    try:
        creds = dict(st.secrets["google_credentials"])
    except (StreamlitSecretNotFoundError, KeyError):
        raise RuntimeError("Google credentials not found in st.secrets")
    return gspread.service_account_from_dict(creds)
```

### Rewrite: app.py demo detection
```python
# BEFORE (current code):
import os
credentials_path = os.path.join(os.path.dirname(__file__), "credentials.json")
is_demo = not os.path.exists(credentials_path)

# AFTER (new code):
from streamlit.errors import StreamlitSecretNotFoundError

try:
    _test = st.secrets["google_credentials"]
    is_demo = False
except (StreamlitSecretNotFoundError, KeyError):
    is_demo = True
```

### Template: .streamlit/secrets.toml
```toml
# Google Service Account Credentials
# -----------------------------------------------
# 1. Go to Google Cloud Console → IAM → Service Accounts
# 2. Create a service account with Editor access to your Google Sheet
# 3. Create a JSON key and download it
# 4. Copy each field from the JSON file into this TOML section
# 5. Restart Streamlit after saving this file
#
# IMPORTANT: This file is in .gitignore — never commit it!

[google_credentials]
type = "service_account"
project_id = "YOUR_PROJECT_ID"
private_key_id = "YOUR_PRIVATE_KEY_ID"
private_key = "-----BEGIN PRIVATE KEY-----\nREPLACE_WITH_YOUR_PRIVATE_KEY\n-----END PRIVATE KEY-----\n"
client_email = "YOUR_SA@YOUR_PROJECT.iam.gserviceaccount.com"
client_id = "YOUR_CLIENT_ID"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/YOUR_SA%40YOUR_PROJECT.iam.gserviceaccount.com"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `oauth2client` for Google auth | `google-auth` library | oauth2client deprecated 2018 | `oauth2client` is unmaintained, has known issues |
| `ServiceAccountCredentials.from_json_keyfile_name()` | `gspread.service_account_from_dict()` | gspread v5.x+ | Reads from dict instead of file path |
| `credentials.json` file | `.streamlit/secrets.toml` | Streamlit 0.82+ (2021) | Native secrets management with TOML format |
| `spreadsheets.google.com/feeds` scope | `www.googleapis.com/auth/spreadsheets` | Sheets API v4 | Old scope was for deprecated API v3 |

**Deprecated/outdated:**
- `oauth2client`: Deprecated since 2018. No longer maintained. `google-auth` is the official replacement.
- `gspread.authorize()`: Still works but `service_account_from_dict()` / `service_account()` are the preferred entry points in v6.x.
- Sheets API v3 scopes (`spreadsheets.google.com/feeds`): Replaced by v4 scopes.

## Impact Analysis — Files That Touch `is_demo` / Credentials

| File | Current Role | Change Required |
|------|-------------|-----------------|
| `config.py:116` | Defines `CREDENTIALS_FILE` | Remove constant. Optionally add `get_google_credentials()` helper. |
| `auth/google_sheets.py:12` | Imports `oauth2client`, `CREDENTIALS_FILE` | Replace import + `get_client()` to use `gspread.service_account_from_dict(dict(st.secrets[...]))` |
| `app.py:47-55` | Detects demo mode via `os.path.exists("credentials.json")` | Detect via `st.secrets` try/except. Update banner text. |
| `requirements.txt:3` | Lists `oauth2client` | Remove line entirely. |
| `.gitignore:19` | Has `.streamlit/secrets.toml` | No change needed. |
| `.streamlit/config.toml` | Streamlit config | No change needed. |
| `components/workspace.py` | Passes `is_demo` to sub-components | No change (receives `is_demo` from app.py, same interface). |
| `components/project_card.py` | Uses `is_demo` to skip writes | No change. |
| `components/todo_card.py` | Uses `is_demo` to skip writes | No change. |

## Open Questions

1. **Should `get_google_credentials()` live in `config.py` or a separate `auth/credentials.py`?**
   - What we know: `config.py` is the central configuration module. Adding secrets access there is logical.
   - Recommendation: Keep it in `config.py` since it's a small helper and avoids creating a new module for one function. The planner can decide otherwise.

2. **Should the Demo Mode banner provide a copy-pasteable secrets.toml template?**
   - What we know: The current banner says "Add your Google Service Account credentials." It could be more helpful.
   - Recommendation: Yes, expand the banner with setup instructions (file path, required fields). The planner should decide the exact UX.

3. **Should `get_client()` cache the gspread client?**
   - What we know: Current code creates a new client for every single API call (each function calls `get_client()` independently). This works but is inefficient.
   - Recommendation: Out of scope for this phase. Document as a future improvement.

## Sources

### Primary (HIGH confidence)
- Streamlit official docs (docs.streamlit.io) — secrets management page verified 2026-04-09
- gspread installed source code — `service_account_from_dict()` signature and implementation inspected via `inspect.getsource()`
- Streamlit installed source code — `StreamlitSecretNotFoundError` behavior verified via live testing
- Current codebase files — all .py files read and analyzed

### Secondary (MEDIUM confidence)
- gspread GitHub releases page (github.com/burnash/gspread/releases) — version history and changelogs verified
- pip registry — version availability confirmed (latest: 6.2.1, installed: 5.12.4)

### Verified by Live Testing
- `st.secrets.get()` raises `StreamlitSecretNotFoundError` when no secrets file exists — **confirmed**
- `key in st.secrets` raises `StreamlitSecretNotFoundError` when no secrets file exists — **confirmed**
- `StreamlitSecretNotFoundError` extends `FileNotFoundError` — **confirmed**
- `gspread.service_account_from_dict(info)` signature: `(info, scopes=DEFAULT_SCOPES, client_factory=None)` — **confirmed**
- gspread internally imports `google.oauth2.service_account.Credentials` (NOT `oauth2client`) — **confirmed**

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified via installed packages and official docs
- Architecture: HIGH — tested `st.secrets` behavior live; gspread API verified via source inspection
- Pitfalls: HIGH — all pitfalls discovered via live testing, not documentation assumptions

**Research date:** 2026-04-09
**Valid until:** 2026-05-09 (stable APIs, unlikely to change)
