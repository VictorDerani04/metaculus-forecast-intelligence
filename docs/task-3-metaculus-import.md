# Task 3: Metaculus URL import

Sign in, create or choose a competition, and paste a Metaculus question URL.
Successful imports show the title, criteria, type, dates, source link and available
binary community probability. Missing values remain unavailable; they never
become zero. Partial metadata is saved with `partial` status. A missing title uses
an explicit `Metaculus question <post ID>` placeholder.

If live access is unavailable, the UI offers manual title and criteria entry.
Saving manual details makes no Metaculus request. The source URL and post ID are
retained, and the record is marked `manual`. Changing the URL clears the old
fallback fields. No forecast is submitted or overwritten.

## Configuration

- `METACULUS_API_TOKEN`: backend environment only. Empty means no live requests.
- `WEB_ORIGIN`: exact frontend origin allowed to make credentialed API requests;
  defaults to `http://localhost:3000`.
- `NEXT_PUBLIC_API_BASE_URL`: frontend API origin; defaults to `http://localhost:8000`.
- Retain the existing private-user, session, database and secure-cookie settings.
  Set the variables in the server environment; the application does not load the
  example file automatically. Keep frontend/API deployments on compatible sites
  for the existing SameSite=Lax session cookie.

The adapter uses authenticated `GET /api/posts/{id}/`, a fixed provider host,
a ten-second timeout, and no redirect following. Authentication failure, rate
limits, provider errors and unusable payloads return a safe manual-entry contract.
There are no automatic retries on throttling. Tests use synthetic fixtures and an
injected HTTP transport, never real credentials or live question data.

Integration fields were checked against the official documentation on 2026-09-07:
- https://www.metaculus.com/api/
- https://github.com/Metaculus/metaculus/blob/main/docs/openapi.yml
- https://www.metaculus.com/terms-of-use/

Use live access only within the account's permissions and the applicable API and
Terms of Use constraints. API availability does not grant permission for AI/ML
training, evaluation or other restricted downstream data uses. This task stores
source data for private question import and does not feed it to AI or models.
Authenticated live access has not been exercised in this checkpoint.

## API and persistence

`POST /competitions/{competition_id}/questions/import`

```json
{"url":"https://www.metaculus.com/questions/45262/"}
```

Manual fallback uses the same endpoint:

```json
{
  "url":"https://www.metaculus.com/questions/45262/",
  "manual_details":{"title":"Question title","resolution_criteria":"Entered criteria"}
}
```

- `201`: saved question and normalized import metadata, including nullable crowd.
- `409`, `detail.code=manual_entry_required`: provider unavailable; no record saved.
- `422`: invalid input; invalid URLs use `detail.code=invalid_url`.
- `401`: session required; `404`: competition unavailable to the current user.

Ownership is checked before fetching or persisting. Source URLs are canonicalized
and source IDs are bounded to the database integer range. Raw provider payloads
are retained separately from manually entered data. Oversized or malformed
optional source fields do not prevent saving the remaining question.

The additive `question_sources` table is keyed by question ID and carries its own
user ID. Existing question/competition tables and records are preserved. The
existing `Base.metadata.create_all` startup creates the new table on the next API
start; no ALTER or destructive migration is required. Existing question-list
response fields are unchanged. Forecast Room retrieval/editing remains Task 4.

## Verification on this Windows checkout

Python dependencies were installed into the ignored `apps/api/.venv/Lib/site-packages`
directory because the selected `py` installation did not contain pytest. This is
a local dependency target, not an activated virtual environment.

From `apps/api` in PowerShell:

```powershell
$env:PYTHONPATH = '.venv/Lib/site-packages'
py -m pytest -q --basetemp (Join-Path '.pytest_cache' ([guid]::NewGuid().ToString()))
```

The unique repository-local temporary directory avoids this machine's restricted
default pytest temporary directory. From `apps/web`:

```powershell
npm.cmd test
npm.cmd run typecheck
npm.cmd run build
```

The source table is PostgreSQL-compatible; automated persistence tests use SQLite.
Known dependency deprecations and the parent package-lock warning remain separate
from Task 3 behavior. No push or deployment is part of this checkpoint.
