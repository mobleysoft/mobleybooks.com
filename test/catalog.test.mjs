import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const catalog = JSON.parse(fs.readFileSync(path.join(root, "catalog", "publications.json"), "utf8"));
const policy = JSON.parse(fs.readFileSync(path.join(root, "catalog", "review-policy.json"), "utf8"));
const prohibited = /(?:erotica|porn|siss|futa|explicit|adult collection|18\+)/i;

test("catalog is an explicit non-empty allowlist", () => {
  assert.equal(policy.default, "deny");
  assert.ok(catalog.titles.length >= 15);
  assert.equal(new Set(catalog.titles.map((entry) => entry.slug)).size, catalog.titles.length);
});

test("every public entry is grounded and workplace-safe", () => {
  for (const entry of catalog.titles) {
    assert.ok(entry.title);
    assert.ok(entry.author);
    assert.ok(entry.description);
    assert.ok(entry.source_kind);
    assert.ok(entry.source_ref);
    assert.ok(Number.isInteger(entry.words) && entry.words > 0);
    if (entry.retail_url) {
      assert.match(entry.retail_url, /^https:\/\/www\.amazon\.com\/dp\/[A-Z0-9]+$/);
    }
    assert.doesNotMatch(JSON.stringify(entry), prohibited);
  }
});

test("verified John Alexander Mobley retail works are represented", () => {
  const retailWorks = catalog.titles.filter(
    (entry) => entry.author === "John Alexander Mobley" && entry.retail_url,
  );
  assert.equal(retailWorks.length, 7);
  assert.deepEqual(
    new Set(retailWorks.map((entry) => entry.slug)),
    new Set([
      "arcane-seven-mission-zero",
      "then-came-man",
      "the-color-of-hope",
      "verdant-vale-aeliana",
      "verdant-vale-day-zero",
      "verdant-vale-heart-s-blossom",
      "verdant-vale-mira",
    ]),
  );
});

test("public catalog contains no private absolute paths", () => {
  assert.doesNotMatch(JSON.stringify(catalog), /\/Users\/|\/Volumes\//);
});
