import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { pathToFileURL } from "node:url";

const root = path.resolve(import.meta.dirname, "..");
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "mobleybooks-worker-"));
const generatedPath = path.join(temporary, "mobleybooks.generated.mjs");
const sourceCatalog = JSON.parse(
  fs.readFileSync(path.join(root, "catalog", "publications.json"), "utf8"),
);
execFileSync(process.execPath, [path.join(root, "tools", "build-worker-module.mjs"), generatedPath]);
const { handleMobleyBooks } = await import(pathToFileURL(generatedPath));

test("renders a searchable specialized library", async () => {
  const response = handleMobleyBooks(new Request("https://mobleybooks.com/"));
  const body = await response.text();
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("x-mobley-edge"), "mobleybooks-library");
  assert.match(body, /Stories with/);
  assert.match(body, /The archive is private/);
  assert.match(body, /Respawn City/);
  assert.match(body, /The New Founding: Friendly Fire/);
  assert.match(body, /Arcane Seven: Mission Zero/);
  assert.match(body, /View published edition/);
  assert.match(body, /https:\/\/www\.amazon\.com\/dp\/B0D8RLP19Z/);
  assert.doesNotMatch(body, /\/Users\/|\/Volumes\//);
});

test("exposes bounded catalog and health endpoints", async () => {
  const catalog = await handleMobleyBooks(new Request("https://mobleybooks.com/catalog.json")).json();
  assert.equal(catalog.title_count, catalog.titles.length);
  assert.equal(catalog.title_count, sourceCatalog.titles.length);
  assert.equal(Object.hasOwn(catalog.titles[0], "source_ref"), false);

  const health = await handleMobleyBooks(new Request("https://mobleybooks.com/health")).json();
  assert.equal(health.status, "ok");
  assert.equal(health.title_count, catalog.title_count);
});

test("fails closed for unsupported mutations and paths", () => {
  assert.equal(handleMobleyBooks(new Request("https://mobleybooks.com/", { method: "POST" })).status, 405);
  assert.equal(handleMobleyBooks(new Request("https://mobleybooks.com/private")).status, 404);
});

test("HEAD returns headers without a body", async () => {
  const response = handleMobleyBooks(new Request("https://mobleybooks.com/", { method: "HEAD" }));
  assert.equal(response.status, 200);
  assert.equal(await response.text(), "");
});
