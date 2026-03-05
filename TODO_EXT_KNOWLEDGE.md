# TODO: External Knowledge Layer Enhancement

## Requirement Summary

Based on `AGENT_EXTERNAL_KNOWLEDGE.md`, the agent needs an **External Knowledge Layer** to extend its capabilities beyond its LLM training cutoff. Without it, the agent may suggest deprecated APIs, miss CVEs, give outdated migration guidance, and be unaware of recent library releases.

The recommended minimal production tool set is:

| Tool | Purpose | Status |
|------|----------|--------|
| Web Search | Broad lookup / fallback | ✅ Exists |
| Package Registry Lookup | Latest versions (PyPI, npm, Cargo) | ❌ Missing |
| GitHub Search | Known bugs, issues, PRs | ❌ Missing |
| Security Advisory Lookup | CVE / vulnerability detection | ❌ Missing |

Tools should be invoked **selectively** — only when the query signals version sensitivity (e.g. keywords: "latest", "deprecated", "upgrade", "CVE", error messages, version numbers).

---

## Implementation Plan

### Files to Change

- `src/cado/agent.py` — all code changes
- `.env.example` — add `GITHUB_TOKEN` entry

No new Python dependencies required. All three APIs are plain JSON REST endpoints; `requests` is already imported.

---

### 1. Add `GITHUB_TOKEN` to config block (after line 70)

```python
# External Knowledge Layer
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
```

---

### 2. Add Three New Tool Functions

Insert after `web_search` (line 578) and before `# WEBSITE READING FUNCTIONS` (line 580).

---

#### `lookup_package_info(package_name: str, registry: str = "pypi") -> Dict[str, Any]`

Queries official package registries for latest version, summary, homepage, and changelog URL.

| Registry | API Endpoint | Notes |
|----------|-------------|-------|
| `pypi` | `GET https://pypi.org/pypi/{package}/json` | No auth |
| `npm` | `GET https://registry.npmjs.org/{package}` | Follow `dist-tags.latest` pointer |
| `cargo` | `GET https://crates.io/api/v1/crates/{package}` | Requires `User-Agent` header |

- 404 response → return `{"error": "..."}` dict (not a RuntimeError)
- npm scoped packages (e.g. `@types/node`): URL-encode name using `urllib.parse.quote(package_name, safe='')`

**Trigger when:** user asks about latest version, changelog, or package existence.

---

#### `search_github(query: str, search_type: str = "repositories") -> List[Dict[str, Any]]`

Searches GitHub via the official Search API.

- **Endpoint:** `GET https://api.github.com/search/{search_type}?q={query}&per_page=8`
- **Auth:** `Authorization: Bearer {GITHUB_TOKEN}` if set (5000/hr vs 60/hr unauthenticated)
- **Required headers:** `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`
- `search_type` options: `"repositories"` (default), `"issues"`, `"code"`
- 403 (rate limit) and 422 (invalid query) → return informational error dict, not RuntimeError
- Issue `body` capped at 500 chars; includes `is_pull_request` flag

**Trigger when:** debugging errors, looking for known upstream bugs, finding official repos.

---

#### `lookup_security_advisory(package_name: str, ecosystem: str = "PyPI") -> List[Dict[str, Any]]`

Queries OSV.dev (open vulnerability database) for known CVEs.

- **Endpoint:** `POST https://api.osv.dev/v1/query`
- **Body:** `{"package": {"name": "...", "ecosystem": "..."}}`
- No auth required
- Normalize ecosystem aliases: `"python"→"PyPI"`, `"rust"→"crates.io"`, `"node"→"npm"`, `"golang"→"Go"`, etc.
- Empty result → return `[{"message": "No known vulnerabilities found..."}]`
- Cap at 10 advisories; `details` capped at 600 chars; max 3 references per advisory
- Supported ecosystems: `PyPI`, `npm`, `crates.io`, `Go`, `Maven`, `NuGet`, `Packagist`, `RubyGems`

**Trigger when:** user mentions CVE/security/vulnerability, before adding a dependency, during upgrade discussions.

---

### 3. Update `SYSTEM_PROMPT` (append before closing `)` on line 151)

Add a third instruction block after the existing Web Search Instructions:

```
## External Knowledge Instructions
You have access to three specialized external knowledge tools. Use them selectively:

### lookup_package_info
Call this when: user asks about latest versions, changelogs, or package existence.
Supported registries: pypi (default), npm, cargo

### search_github
Call this when: debugging errors that may be upstream bugs, finding official repos,
checking known issues/PRs. Supported search_type: repositories (default), issues, code

### lookup_security_advisory
Call this when: user mentions CVE/security/vulnerability, before recommending a
new dependency, or when a package upgrade is being discussed.
Supported ecosystems: PyPI (default), npm, crates.io, Go, Maven, NuGet, Packagist, RubyGems

Do NOT call these tools for every request. Invoke only when the user intent
clearly benefits from authoritative, version-aware, or security-specific information.
```

---

### 4. Update `Agent(tools=[...])` registration (lines 761–774)

Add three new entries after `web_search`:

```python
lookup_package_info,
search_github,
lookup_security_advisory,
```

---

### 5. Update `.env.example`

Add a new section:

```
# External Knowledge Layer
# GitHub API Token (optional) - raises rate limit from 60/hr to 5000/hr
# Create at: https://github.com/settings/tokens (no special scopes needed for public search)
GITHUB_TOKEN=your_github_token_here
```

---

## Verification

1. **Package lookup (PyPI):** Ask "What is the latest version of pydantic-ai?" → should call `lookup_package_info("pydantic-ai", "pypi")`
2. **Package lookup (npm):** Ask "What's the latest version of express on npm?" → should call `lookup_package_info("express", "npm")`
3. **GitHub issues search:** Ask "Are there known memory leak issues in pydantic?" → should call `search_github("pydantic memory leak", "issues")`
4. **Security advisory:** Ask "Is the requests library safe? Any known CVEs?" → should call `lookup_security_advisory("requests", "PyPI")`
5. **No over-triggering:** Ask "Write a Python hello world" → no external knowledge tools should be called
