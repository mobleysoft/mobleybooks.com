#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const catalogPath = path.join(root, "catalog", "publications.json");
const templatePath = path.join(root, "src", "mobleybooks.template.js");
const outputPath = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.join(root, "dist", "mobleybooks.generated.js");

const catalog = JSON.parse(fs.readFileSync(catalogPath, "utf8"));
const template = fs.readFileSync(templatePath, "utf8");
if (!Array.isArray(catalog.titles) || catalog.titles.length === 0) {
  throw new Error("catalog must contain at least one explicitly approved title");
}
for (const entry of catalog.titles) {
  if (entry.retail_url && !/^https:\/\/www\.amazon\.com\/dp\/[A-Z0-9]+$/.test(entry.retail_url)) {
    throw new Error(`invalid retail URL for ${entry.slug}`);
  }
}

const publicShape = {
  schema_version: catalog.schema_version,
  updated_at: catalog.updated_at,
  title_count: catalog.titles.length,
  titles: catalog.titles.map(({ source_ref: _sourceRef, ...entry }) => entry),
};
const generated = template.replace(
  "__MOBLEYBOOKS_CATALOG__",
  JSON.stringify(publicShape),
);
if (generated.includes("__MOBLEYBOOKS_CATALOG__")) {
  throw new Error("catalog placeholder was not replaced");
}

fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.writeFileSync(outputPath, generated);
process.stdout.write(`${outputPath}\n`);
