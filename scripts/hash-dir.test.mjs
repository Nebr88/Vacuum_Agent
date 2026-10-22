/**
 * hashDir is a CACHE-BUST TOKEN generator, so it has two jobs that pull against
 * each other: change when the content changes, and NOT change otherwise. These
 * tests pin both directions, because an implementation that only ever returns the
 * same string would satisfy "no spurious churn" perfectly and be useless.
 *
 * The input that made HD-1 red: a locales dir checked out as CRLF rather than LF.
 * Git reports both as clean (`core.autocrlf=true` normalizes before comparing), so
 * nothing else in the toolchain can see the difference — see scripts/hash-dir.mjs.
 *
 * Run: node --test scripts/hash-dir.test.mjs
 */
import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, readdirSync, statSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { hashDir, normalizeForHash } from "./hash-dir.mjs";

const TEXTURES_DIR = "custom_components/eufy_vacuum/textures";

/** The OLD implementation: raw bytes, no normalization. The reference we diverge from. */
function hashDirRaw(dir) {
  const h = createHash("sha1");
  const walk = (d) => {
    for (const name of readdirSync(d).sort()) {
      const p = join(d, name);
      if (statSync(p).isDirectory()) walk(p);
      else {
        h.update(name);
        h.update(readFileSync(p));
      }
    }
  };
  walk(dir);
  return h.digest("hex").slice(0, 10);
}

/** Build a throwaway dir; files is {name: Buffer|string}, "/" in a name makes a subdir. */
function fixture(files) {
  const root = mkdtempSync(join(tmpdir(), "hashdir-"));
  for (const [name, body] of Object.entries(files)) {
    const p = join(root, name);
    if (name.includes("/")) mkdirSync(join(p, ".."), { recursive: true });
    writeFileSync(p, body);
  }
  return root;
}

const CATALOG_LF = '{\n  "a.b": "one",\n  "c.d": "two"\n}\n';
const CATALOG_CRLF = CATALOG_LF.replace(/\n/g, "\r\n");
// A NUL makes it binary, and the 0D 0A pair is real content - exactly the shape of
// every texture PNG in this repo (measured: 1-119 occurrences of 0D 0A per file).
const BINARY_CRLF = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x00, 0x0d, 0x0a, 0x1a, 0x0a]);
const BINARY_LF = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x00, 0x0a, 0x1a, 0x0a]);

test("[HD-1] line endings do NOT move the token — the whole point", () => {
  const lf = fixture({ "en.json": CATALOG_LF, "README.md": "hello\nworld\n" });
  const crlf = fixture({ "en.json": CATALOG_CRLF, "README.md": "hello\r\nworld\r\n" });
  try {
    assert.equal(hashDir(lf), hashDir(crlf));
    // and prove the fixture really differs on disk, or HD-1 proves nothing
    assert.notEqual(hashDirRaw(lf), hashDirRaw(crlf), "fixture is not actually CRLF vs LF");
  } finally {
    rmSync(lf, { recursive: true, force: true });
    rmSync(crlf, { recursive: true, force: true });
  }
});

test("[HD-2] a BINARY file's 0D 0A is content, not a line ending", () => {
  const a = fixture({ "t.png": BINARY_CRLF });
  const b = fixture({ "t.png": BINARY_LF });
  try {
    // Normalizing unconditionally would make these equal and the token lossy.
    assert.notEqual(hashDir(a), hashDir(b));
    assert.ok(normalizeForHash(BINARY_CRLF).equals(BINARY_CRLF), "binary was rewritten");
  } finally {
    rmSync(a, { recursive: true, force: true });
    rmSync(b, { recursive: true, force: true });
  }
});

test("[HD-3] a real content change STILL busts the token", () => {
  const a = fixture({ "en.json": CATALOG_LF });
  const b = fixture({ "en.json": CATALOG_LF.replace("one", "uno") });
  try {
    assert.notEqual(hashDir(a), hashDir(b));
  } finally {
    rmSync(a, { recursive: true, force: true });
    rmSync(b, { recursive: true, force: true });
  }
});

test("[HD-4] a rename busts the token (the URL carries the name)", () => {
  const a = fixture({ "en.json": CATALOG_LF });
  const b = fixture({ "fr.json": CATALOG_LF });
  try {
    assert.notEqual(hashDir(a), hashDir(b));
  } finally {
    rmSync(a, { recursive: true, force: true });
    rmSync(b, { recursive: true, force: true });
  }
});

test("[HD-5] text and binary mix, and subdirs recurse — the real shape", () => {
  const lf = fixture({ "en.json": CATALOG_LF, "sub/t.png": BINARY_CRLF, "sub/x.json": CATALOG_LF });
  const crlf = fixture({ "en.json": CATALOG_CRLF, "sub/t.png": BINARY_CRLF, "sub/x.json": CATALOG_CRLF });
  try {
    assert.equal(hashDir(lf), hashDir(crlf), "text in a subdir must normalize too");
  } finally {
    rmSync(lf, { recursive: true, force: true });
    rmSync(crlf, { recursive: true, force: true });
  }
});

test("[HD-6] normalization is a NO-OP on the SHIPPED textures", () => {
  // Real data, not a fixture: if normalization ever touched these, the texture
  // cache-bust token would shift for every user and stop tracking the image bytes.
  assert.equal(hashDir(TEXTURES_DIR), hashDirRaw(TEXTURES_DIR));
});
