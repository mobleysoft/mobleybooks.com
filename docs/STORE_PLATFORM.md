# Store Platform

MobleyBooks is the publisher and catalog authority. It should not absorb every
subsidiary implementation. Instead, each venture contributes one narrow cowlick
through the contract in `catalog/store-platform.json`.

## Core path

1. Unlost discovers and grounds a source.
2. Apex April completes or edits an immutable copy through an emitted profile.
3. MobleyBooks approves metadata, editions, rights state, and publication.
4. LiteraCraft supplies the premium exclusive-fiction reader and serialization layer.
5. SingularityUI renders the store, library, reader, and checkout surfaces.
6. Authfor identifies the customer and evaluates access entitlements.
7. VendyAI creates the order and delegates payment processing to the configured provider.
8. Bookeepr records revenue, refunds, royalties, and settlements.
9. Consenta enforces consent, privacy, retention, and deletion policy.
10. MailGuyAI sends transactional messages; Marketingium handles attributed acquisition.

BookClubs adds community and discovery. GlyphyAI and AudiovizAI create approved
edition assets. Book2Film expands adaptation rights. GLCX controls legal terms
and rights-chain review. MobleyReport can cover releases but cannot approve them.

## Boundary

“Planned integration” is not “live.” Each interface requires contract tests,
failure handling, observability, and a production evidence record. A purchase is
complete only when payment, entitlement, receipt, ledger, refund, and privacy
flows all pass end to end.
