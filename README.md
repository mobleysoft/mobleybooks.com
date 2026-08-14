# MobleyBooks

Canonical source for the public `mobleybooks.com` title library.

The catalog is default-deny. Unlost, the Dell replica, and Google Drive can
discover candidates, but only explicitly reviewed entries in
`catalog/publications.json` are permitted in the public bundle. Mature,
private, or unverified material must never be copied into the catalog, tests,
generated Worker module, logs, or public source.

```sh
node --test test/*.test.mjs
node tools/build-worker-module.mjs ../nginx/workers/venture-fleet/src/mobleybooks.generated.js
```

The generated module is imported by the account-local venture fleet Worker so
MobleyBooks receives a specialized product surface without consuming another
Cloudflare Worker slot. Deployment remains canary-first and must be followed
by public HTTPS verification of the apex, `www`, health, and catalog routes.
