# read-real-code

Weekly code-reading picker. One bookmarked URL hands you one repo, one entry point, and a short reading list — deterministic from the current ISO week.

See [SPEC.md](./SPEC.md) for the full design.

## Add a repo

1. Add an entry to `data/repos.json` matching `data/schema.json`.
2. Open a PR. CI validates schema, duplicate ids, and (best-effort) URL/ref reachability.
3. Merge → live on the next page load.

## Validate locally

```sh
node scripts/validate.mjs           # schema + duplicates (offline, fast)
node scripts/validate.mjs --strict  # adds URL + ref HEAD checks (network, flaky)
```

Strict mode is best-effort: failures are logged as warnings, not errors. CI runs it under `continue-on-error: true`.
