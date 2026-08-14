# MobleyBooks

Canonical source for the public `mobleybooks.com` title library.

The catalog is default-deny. Unlost, the Dell replica, and Google Drive can
discover candidates, but only explicitly reviewed entries in
`catalog/publications.json` are permitted in the public bundle. Mature,
private, or unverified material must never be copied into the catalog, tests,
generated Worker module, logs, or public source.

Retail links are allowed only when an authenticated KDP record confirms the
edition and the URL is a canonical Amazon ASIN route. A retail record does not
override the editorial allowlist.

Private estate reconciliation and per-work April profile emission are documented
in `docs/LIBRARY_RECONCILIATION.md`. The bounded subsidiary interfaces for the
future direct store are documented in `docs/STORE_PLATFORM.md` and
`catalog/store-platform.json`.

```sh
node --test test/*.test.mjs
python3 -m unittest discover -s test -p 'test_*.py'
python3 tools/library_reconciler.py --strict
node tools/build-worker-module.mjs ../nginx/workers/venture-fleet/src/mobleybooks.generated.js
```

The generated module is imported by the account-local venture fleet Worker so
MobleyBooks receives a specialized product surface without consuming another
Cloudflare Worker slot. Deployment remains canary-first and must be followed
by public HTTPS verification of the apex, `www`, health, and catalog routes.
