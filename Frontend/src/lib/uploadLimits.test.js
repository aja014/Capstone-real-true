import { test } from "node:test";
import assert from "node:assert/strict";
import { FILE_TOO_LARGE, MAX_UPLOAD_BYTES, isTooLarge } from "./uploadLimits.js";

test("the limit is 10 MB, the same as the backend", () => {
  assert.equal(MAX_UPLOAD_BYTES, 10 * 1024 * 1024);
  assert.equal(FILE_TOO_LARGE, "File is too large (max 10 MB).");
});

test("exactly 10 MB is allowed, one byte more is not", () => {
  assert.equal(isTooLarge({ size: MAX_UPLOAD_BYTES }), false);
  assert.equal(isTooLarge({ size: MAX_UPLOAD_BYTES + 1 }), true);
  assert.equal(isTooLarge({ size: 0 }), false);
});
