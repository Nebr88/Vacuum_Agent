/**
 * Content hash of a directory tree: name + bytes of every file. Used as a
 * cache-bust token so a CHANGE to the assets yields a new ?v=<hash> URL (browsers
 * + HA's service worker fetch fresh) while UNCHANGED assets keep one stable URL
 * (stay cached, no churn). Same scheme for textures and for the runtime locale
 * catalogs (which are fetched at runtime, NOT bundled, so they need their own bust).
 *
 * THE TOKEN MUST BE A FUNCTION OF CONTENT. It used to be a function of the BYTES
 * IN THE BUILDING CHECKOUT, which is not the same thing, and the gap is invisible
 * by construction: with `core.autocrlf=true` a text file can sit on disk as LF or
 * as CRLF and git calls BOTH clean, because it normalizes before comparing. So
 * `git status` can never report the drift, while a raw-bytes hash sees it.
 *
 * Measured on ONE commit, the locales dir, nothing modified, four different tokens:
 *
 *   e0964d6deb   the main checkout      (git: i/lf w/lf for the catalogs, w/crlf README)
 *   98525d31ca   a fresh worktree       (git: i/lf w/crlf throughout)
 *   e9ea9da997   that worktree mid-build, en.reference.jsonc freshly GENERATED as LF
 *   bef0c520ac   any uniformly-LF tree
 *
 * This never caused stale translations — within one tree a content change always
 * changes the token — so the cost was a spurious cache-bust for every user on any
 * rebuild from a different tree, plus a bundle diff that could not be reproduced
 * across machines. Normalizing CRLF to LF for text makes the token depend on the
 * committed content and nothing else.
 *
 * NORMALIZE TEXT ONLY, and this is the part that bites. Every texture PNG in this
 * repo contains the byte pair 0D 0A somewhere in its compressed data — measured, 1
 * to 119 occurrences per file. Collapsing those would rewrite the texture token and
 * make it a LOSSY function of the image, which is the opposite of what a cache-bust
 * key is for. Binary is detected by a NUL byte: every PNG header has one, no JSON
 * catalog does. That is git's own heuristic, and it is why the texture token was the
 * one that matched everywhere while the locale token did not.
 */
import { createHash } from "node:crypto";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const NUL = 0;
const CRLF = Buffer.from([0x0d, 0x0a]);
const LF = 0x0a;
const CR = 0x0d;

/** Raw bytes for binary, CRLF folded to LF for text. See the header. */
export function normalizeForHash(buf) {
  if (buf.includes(NUL)) return buf; // binary — the bytes ARE the content
  if (buf.indexOf(CRLF) === -1) return buf; // already LF-only, nothing to fold
  const out = Buffer.allocUnsafe(buf.length);
  let n = 0;
  for (let i = 0; i < buf.length; i++) {
    if (buf[i] === CR && buf[i + 1] === LF) continue; // drop the CR, keep the LF
    out[n++] = buf[i];
  }
  return out.subarray(0, n);
}

export function hashDir(dir) {
  const h = createHash("sha1");
  const walk = (d) => {
    for (const name of readdirSync(d).sort()) {
      const p = join(d, name);
      const st = statSync(p);
      if (st.isDirectory()) walk(p);
      else {
        h.update(name);          // name matters (URL changes if a file is renamed)
        h.update(normalizeForHash(readFileSync(p))); // content, not line endings
      }
    }
  };
  walk(dir);
  return h.digest("hex").slice(0, 10);
}
