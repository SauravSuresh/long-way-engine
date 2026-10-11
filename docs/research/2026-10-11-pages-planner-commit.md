# Research: committing a repo file from a static GitHub Pages planner (#7)

Date: 2026-10-11. Part of #6. Question: what does a static page served from
GitHub Pages need to read and update a file in this repo through the GitHub
REST contents API with a fine-grained personal access token (PAT), and does it
work from a phone browser?

Sources are docs.github.com (primary), plus live probes against api.github.com
and the deployed Pages site on 2026-10-11 where the docs were silent. Probe
commits were made on a scratch branch `tmp/sha-probe`, which was deleted.

**Verdict: viable, including from a phone.** No hard blocker found. Two
operational caveats: Safari deletes `localStorage` after 7 days without a
visit (token re-entry), and Pages caches for 10 minutes (read through the API,
not the Pages URL, if you need the latest file).

## 1. Token: fine-grained PAT, Contents read/write on one repo

- Fine-grained PATs work with both contents endpoints. The reference page lists
  "Fine-grained personal access tokens" under "This endpoint works with the
  following fine-grained token types" for both GET and PUT.
  - GET `/repos/{owner}/{repo}/contents/{path}`: "The fine-grained token must
    have the following permission set: 'Contents' repository permissions
    (read)". Public repos can be read without a token at all.
  - PUT `/repos/{owner}/{repo}/contents/{path}`: "The fine-grained token must
    have at least one of the following permission sets: 'Contents' repository
    permissions (write)" (or Contents write + Workflows write, only needed when
    the file is under `.github/workflows`).
  - https://docs.github.com/en/rest/repos/contents?apiVersion=2022-11-28
- Same facts in the permissions table: GET contents = read, PUT contents = write.
  https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens?apiVersion=2022-11-28
- Fine-grained PATs can be scoped to one repository with only the chosen
  permissions; GitHub recommends them over classic tokens. Default lifetime is
  30 days; a non-expiring token is allowed for a personal account (an org
  policy may cap it, not relevant here). The owner's own repo is not in the
  "not yet supported" list (outside collaborator, Packages, Checks, user
  Projects).
  https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens
- Header: `Authorization: Bearer <token>` (or `Authorization: token <token>`).
  https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api?apiVersion=2022-11-28
- So: one fine-grained PAT, repository access = `long-way-engine` only,
  permission = Contents: Read and write (Metadata: read is auto-added). Nothing
  else.

## 2. Read -> sha -> PUT flow, conflicts, size limits

Documented at https://docs.github.com/en/rest/repos/contents?apiVersion=2022-11-28

1. `GET /repos/O/R/contents/docs/data/catalog.json?ref=main` with
   `Accept: application/vnd.github+json`. Response has `content` (base64, may
   contain newlines) and `sha` (blob SHA). 404 if the file does not exist yet.
2. `PUT /repos/O/R/contents/docs/data/catalog.json` with JSON body
   `{ "message", "content": <base64>, "sha": <blob sha from step 1>, "branch": "main" }`.
   - `content` is "The new file content, using Base64 encoding."
   - `sha` is "Required if you are updating a file. The blob SHA of the file
     being replaced." Omit it only when creating a new file.
   - `branch` defaults to the default branch.
   - `committer`/`author` optional; if given, both `name` and `email` are
     required or you get 422.
3. Status codes listed for PUT: 200 OK (update), 201 Created (new file),
   404, 409 Conflict, 422 "Validation failed, or the endpoint has been spammed".

Stale-sha behaviour is not spelled out in the docs beyond "409 Conflict", so it
was probed live (scratch branch, 2026-10-11):

| Request | Result |
|---|---|
| PUT new file, no `sha` | `201` |
| PUT existing file, correct `sha` | `200` |
| PUT existing file, **stale** `sha` | `409` `{"message":"tmp-probe.json does not match <sha>"}` |
| PUT existing file, **no** `sha` | `422` `{"message":"Invalid request.\n\n\"sha\" wasn't supplied."}` |

Handling: on 409, re-GET, re-apply the edit on the fresh content, PUT again
with the new sha. The docs also warn: concurrent PUT/DELETE on the same path
"will conflict and you will receive errors. You must use these endpoints
serially instead." One planner user on one phone is serial by construction.

Size limits:
- GET: "1 MB or smaller: All features of this endpoint are supported. Between
  1-100 MB: Only the raw or object custom media types are supported" (`content`
  comes back empty with the JSON media type). "Greater than 100 MB: This
  endpoint is not supported." Directory listings cap at 1,000 entries.
- Repo-wide: "GitHub blocks files larger than 100 MiB", warning above 50 MiB.
  https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github
- `catalog.json` is a few KB; keep it under 1 MB and the JSON media type works
  end to end. If it ever grows past 1 MB, read with
  `Accept: application/vnd.github.raw+json` instead.

Browser detail: `btoa()` only accepts Latin-1. For UTF-8 JSON encode via
`new TextEncoder().encode(str)` -> bytes -> base64 (and the reverse on read, or
fetch the raw media type and skip base64 for reads). Not a GitHub limit, a JS one.

## 3. CORS from api.github.com

- Docs: the REST API "supports cross-origin resource sharing (CORS) for AJAX
  requests from any origin"; the sample preflight shows
  `Access-Control-Allow-Origin: *`, `Access-Control-Allow-Headers` including
  `Authorization, Content-Type`, `Access-Control-Allow-Methods: GET, POST,
  PATCH, PUT, DELETE`, `Access-Control-Max-Age: 86400`.
  https://docs.github.com/en/rest/using-the-rest-api/using-cors-and-jsonp-to-make-cross-origin-requests?apiVersion=2022-11-28
- Live preflight on 2026-10-11 (`OPTIONS .../contents/README.md` with
  `Origin: https://sauravsuresh.github.io`, requested method PUT, requested
  headers `authorization,content-type`) returned `204` with exactly those
  headers, plus `Access-Control-Expose-Headers` listing `ETag` and all
  `X-RateLimit-*` headers, so the page can read them.
- A hand-set `Authorization` header is a plain request header for CORS
  purposes (not a cookie credential), so the `*` origin is fine. Do not set
  `credentials: 'include'`; the default is enough.

## 4. Rate limits (authenticated user)

- Primary: 5,000 requests/hour per user for PAT-authenticated requests
  (unauthenticated: 60/hour per IP). Exceeding returns 403 or 429 with
  `x-ratelimit-remaining: 0`; wait until `x-ratelimit-reset`.
- Secondary, content-creating requests (a PUT is one): "no more than 80
  content-generating requests per minute and no more than 500 content-generating
  requests per hour."
- https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api?apiVersion=2022-11-28
- Confirmed live: `x-ratelimit-limit: 5000` with a token, `60` without.
- A planner doing a handful of GET+PUT pairs per day is 3 orders of magnitude
  under both limits.

## 5. Does a contents-API commit trigger the daily engine?

- This repo's workflows (`.github/workflows/`, read on `origin/main`):
  - `daily.yml`: `on: schedule` (cron `30 21 * * *`) and `workflow_dispatch`
    only. **No `push` trigger.** A contents-API commit will not run the engine;
    it keeps running on its 03:00 IST cron (and can be run manually via
    `workflow_dispatch`). The engine commits `docs/index.html`,
    `docs/assets/data.json`, `.task_cache.json`, `LOG.md`, `state/`,
    `reflections/`; it does not touch `docs/data/`, so there is no write race
    with the planner's file (beyond the ordinary stale-sha 409 if both commit
    to `main` in the same instant, which the retry in section 2 handles).
  - `test.yml`: `on: push: branches: [main]` with no path filter. **A
    contents-API commit to `main` will run pytest** (harmless, costs one
    Actions minute-ish). Add `paths-ignore: ['docs/**']` if that is unwanted.
  - `repopick-validate.yml`: push to `main` only for `docs/repopick/data/**`
    and its script; `docs/data/catalog.json` does not match.
- Why it counts as a push: the contents API creates a commit and advances the
  branch ref, which is a push event. Actions `push` fires when you "push a
  commit or tag".
  https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#push
  Confirmed live: the probe PUT produced a `PushEvent` on
  `refs/heads/tmp/sha-probe` in `GET /repos/O/R/events`.
- The "commits from `GITHUB_TOKEN` do not create new workflow runs" rule does
  not apply: a PAT commit is a normal user push.
  https://docs.github.com/en/actions/concepts/security/github_token
- Pages build: a PAT push to `main` also triggers the Pages build (this repo
  is `build_type: legacy`, source `main:/docs`). The Pages docs say
  `GITHUB_TOKEN` pushes "do not trigger a GitHub Pages build", but
  `pages-build-deployment` runs are observed right after each bot commit here,
  so in practice both bot and PAT commits rebuild the site.
  https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site

## 6. Pages caching / propagation for a freshly pushed `docs/data/catalog.json`

- Publish delay: "It can take up to 10 minutes for changes to your site to
  publish after you push the changes to GitHub."
  https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site
  Observed: `pages-build-deployment` finished ~16 s after the daily commit
  (00:16:13 -> 00:16:29 UTC on 2026-10-11).
- Limits: "soft limit of 10 builds per hour" (does not apply with a custom
  Actions workflow), 1 GB site, 100 GB/month soft bandwidth, deployments time
  out at 10 minutes.
  https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits
- CDN cache: GitHub does not document it. Live headers for
  `https://sauravsuresh.github.io/long-way-engine/assets/data.json`:
  `cache-control: max-age=600`, `via: 1.1 varnish`, `x-served-by: cache-maa...`,
  `etag`, `last-modified`. So a browser or edge may serve a stale file for up
  to 10 minutes after deploy, on top of the deploy time.
- Consequence for the planner: do not read `catalog.json` from the Pages URL
  to get the sha-current version; read it from the API (section 2), which is
  never cached and is what the PUT's `sha` must come from. The Pages URL is
  fine for passive viewers; append a cache-buster (`?v=<timestamp>`) or send
  `cache: 'no-store'` if a viewer needs it fresher than 10 minutes.
- Each planner PUT costs one Pages build; 10 builds/hour soft limit means
  "save on every keystroke" is out, "save on explicit button" is fine.

## 7. Phone browser (iOS Safari/Chrome, Android Chrome) blockers

None hard. Things to design around:

- **Safari 7-day storage cap.** WebKit deletes all script-writable storage
  (LocalStorage, IndexedDB, SessionStorage, service-worker cache) "after seven
  days of Safari use without user interaction on the site". A token stored in
  `localStorage` will vanish if the planner is not opened for a week of Safari
  use. Exemption: "Web applications added to the home screen are not part of
  Safari and thus have their own counter of days of use", so an Add to Home
  Screen install avoids it. iOS Chrome uses WebKit and inherits this.
  https://webkit.org/blog/10218/full-third-party-cookie-blocking-and-more/
  Mitigation: home-screen install, or just re-paste the token when missing
  (one field, one time a week at worst).
- **Token entry.** Creating the fine-grained PAT happens on github.com
  (Settings -> Developer settings), which works in a mobile browser; pasting a
  ~90-char token into an input is the only manual step. Token expiry (default
  30 days; set to no expiration or 1 year for a personal account) means an
  occasional re-paste.
- **Token exposure.** The token lives in the phone's browser storage and in
  the page's memory. The page is public on Pages but the token never leaves the
  device except to api.github.com over TLS. Scope it to one repo, Contents
  only, so a leak at worst rewrites files in this repo (recoverable via git
  history). Don't commit it into the page.
- Everything else is standard `fetch()` with a custom header, supported on all
  current mobile browsers; CORS is server-side and confirmed above.
- No branch protection or rulesets on `main` (checked via API), so a direct
  PUT to `main` is accepted.

## Minimal client sketch (for #6)

```js
const API = 'https://api.github.com/repos/SauravSuresh/long-way-engine/contents/docs/data/catalog.json';
const hdr = t => ({ Authorization: `Bearer ${t}`, Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28' });
const b64enc = s => btoa(String.fromCharCode(...new TextEncoder().encode(s)));
const b64dec = b => new TextDecoder().decode(Uint8Array.from(atob(b.replace(/\n/g, '')), c => c.charCodeAt(0)));

async function load(token) {
  const r = await fetch(`${API}?ref=main`, { headers: hdr(token) });
  if (r.status === 404) return { sha: null, data: {} };
  const j = await r.json();
  return { sha: j.sha, data: JSON.parse(b64dec(j.content)) };
}
async function save(token, sha, data, message) {
  const body = { message, branch: 'main', content: b64enc(JSON.stringify(data, null, 2) + '\n') };
  if (sha) body.sha = sha;
  const r = await fetch(API, { method: 'PUT', headers: hdr(token), body: JSON.stringify(body) });
  if (r.status === 409) throw new Error('stale sha: reload and retry');
  if (!r.ok) throw new Error(`${r.status} ${(await r.json()).message}`);
  return (await r.json()).content.sha;   // new blob sha for the next save
}
```
