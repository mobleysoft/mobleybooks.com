# Library Reconciliation

MobleyBooks treats discovery, completion, editorial approval, and publication as
separate state transitions. A file is not automatically a work, and a work is
not automatically a public book.

## Why omissions happened

The previous catalog pass searched selected authors and known titles instead of
reconciling an authoritative private KDP inventory. It also used one author
spelling, retained no durable review queue, and tested a hardcoded list of seven
retail works. Default-deny correctly prevented unsafe publication, but silently
discarded safe omissions because there was no private candidate ledger.

`tools/library_reconciler.py` corrects that failure mode:

1. Read every prose-capable artifact from the local and Dell Unlost shards.
2. Score likely manuscript paths without claiming every document is a book.
3. Separate authored candidates, support material, uncertain candidates, and
   legacy machine-generated output.
4. Group revisions by normalized title while retaining every source reference.
5. Measure readable source text, estimate a provisional target, and enumerate
   the remaining editorial gates.
6. Compare the public retail catalog with a private KDP inventory, including
   author aliases and explicit exclusions.
7. Emit one immutable-source April profile per candidate under private state.

## Run

```sh
python3 tools/library_reconciler.py --strict
```

Private outputs are written to:

```text
~/.local/share/mobleybooks/reconciliation/latest.json
~/.local/share/mobleybooks/reconciliation/latest.md
~/.local/share/mobleybooks/april-profiles/*.json
~/.local/share/mobleybooks/april-output/<work-id>/
```

The tool does not mutate manuscripts, edit `catalog/publications.json`, or
deploy. The public catalog remains an explicit SFW allowlist.

## April specializations

The emitted “versions” are profiles over the single shared Apex April engine,
not copied scripts. This prevents the April lineage from fragmenting again.

- `series-continuity-completion`: preserve canon across an established series.
- `fragment-expansion`: turn a treatment or fragment into a reviewed structure.
- `short-form-completion`: close gaps in short fiction and novellas.
- `novel-completion`: map and draft missing scenes in substantial manuscripts.
- `editorial-and-release`: polish a complete manuscript without inventing a new one.
- `legacy-output-rehabilitation`: quarantine and assess historical generated output.

Every profile records the source fingerprint, forbids source mutation, writes to
a separate output root, and requires explicit publication approval.

## Current limits

The inventory is only as complete as Unlost's sources. Apple Notes, unconnected
Google Drive accounts, KDP pages not yet captured, and unhydrated provider files
remain outside a fully verified estate-wide count. The report therefore exposes
raw artifact count, candidate work count, and approved catalog count separately.
