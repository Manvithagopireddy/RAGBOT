# Security Policy

RAGBOT is designed with a defense-in-depth architecture adhering to OWASP API Security and Generative AI Security standards.

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.0.x   | :white_check_mark: |
| < 2.0.0 | :x:                |

## Security Architecture & Defenses

### 1. Authentication & Authorization
- **Strict JWT Verification**: All sensitive API endpoints require cryptographically signed Bearer tokens.
- **Algorithm Whitelisting**: Restricted to `HS256`, `HS384`, `HS512`. The insecure `'none'` algorithm and asymmetric confusion attacks are strictly rejected.
- **Fail-Secure Key Management**: Production environments require a cryptographically random `JWT_SECRET_KEY` (minimum 32 bytes) configured via environment variables; the application refuses to boot if unconfigured.
- **No Unauthenticated Privileges**: There is no default administrator fallback or mock user bypass. All access without a valid token receives `HTTP 401 Unauthorized`.

### 2. Multi-Tenant Data Isolation
- **Catalog-Backed Retrieval Filtering**: While FAISS and BM25 utilize optimized in-memory vector stores, retrieval candidates are explicitly filtered by `user_id` cross-referenced with the user's verified document catalog in SQLite.
- **Resource Ownership Validation**: Endpoints (`/api/v1/sessions/*`, `/api/v1/documents/*`) enforce resource ownership. Access to resources belonging to another user returns `HTTP 404 Not Found` to prevent identity enumeration.
- **Zero Data Leakage on Deletion**: Deleting a document purges its file on disk, its catalog record in SQLite, and immediately rebuilds the in-memory FAISS and BM25 indexes excluding the deleted document's chunks.

### 3. Prompt Injection & Adversarial Defenses
- **Defensive Demarcation**: Retrieved document context is encapsulated within `<context_documents>` XML tags with explicit instruction boundaries directing the model to treat content purely as untrusted data.
- **Adversarial Pattern Redaction**: Known jailbreak patterns (`ignore previous instructions`, `system prompt override`, `developer mode`, role spoofing markers) are intercepted and neutralized.
- **Strict Context Token Budgeting**: Enforces token ceilings to prevent context overflow attacks and prompt displacement.

### 4. Input & Upload Validation
- **Magic Byte Verification**: File uploads undergo magic number inspection to prevent malicious binaries (PE, ELF, Mach-O) disguised under safe file extensions (`.pdf`, `.txt`, `.docx`).
- **Payload Size Limits**: Global middleware rejects requests exceeding size limits (25MB for document uploads, 2MB for standard JSON endpoints) returning `HTTP 413 Content Too Large`.
- **Sliding-Window Rate Limiting**: In-memory rate limiting (60 RPM default) throttles excessive requests per IP/identity.

### 5. Automated Security Gates in CI
Every pull request and commit must pass automated security workflows:
- **Bandit AST Security Scanner**: Zero Medium or High severity issues permitted.
- **Pip-Audit**: Continuous CVE scanning against PyPI vulnerability advisories.
- **Automated Security Test Suite**: 209 unit and integration security tests.

## Reporting a Vulnerability

If you discover a security vulnerability within RAGBOT, please report it privately:
- **Email**: `security@ragbot.local` or contact the maintainer directly on GitHub.
- **Response Time**: We acknowledge receipt of vulnerability reports within 24 hours and aim to provide patches within 72 hours.
- Please do **not** open public issues for security vulnerabilities until a fix has been released.
