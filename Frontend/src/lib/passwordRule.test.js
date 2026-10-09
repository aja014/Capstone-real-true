import { test } from "node:test";
import assert from "node:assert/strict";
import {
  PASSWORD_HAS_USERNAME_MESSAGE, PASSWORD_HINT, PASSWORD_RULE_MESSAGE, PASSWORD_TOO_LONG_MESSAGE,
  containsUsername, passwordHint, passwordRuleError,
} from "./passwordRule.js";

const HOSTED = { minLength: 12, blockCommon: true };

test("defaults keep today's rule and texts (8 characters, 2 letters, no username check)", () => {
  assert.equal(PASSWORD_HINT, "At least 8 characters, including 2 letters");
  assert.equal(PASSWORD_RULE_MESSAGE, "Password must be at least 8 characters and include at least 2 letters.");
  assert.equal(passwordRuleError("ab345678"), null);
  assert.equal(passwordRuleError("ab34567"), PASSWORD_RULE_MESSAGE);
  assert.equal(passwordRuleError("1234567a"), PASSWORD_RULE_MESSAGE);
  assert.equal(passwordRuleError("zztestjuliet1", "ZZTEST Juliet"), null);
  assert.equal(passwordRuleError("ab" + "1".repeat(71)), PASSWORD_TOO_LONG_MESSAGE);
});

test("hosted rule: 12 characters, and the hint says so", () => {
  assert.equal(passwordHint(HOSTED), "At least 12 characters, including 2 letters. Not a common password, and not your username.");
  assert.equal(passwordRuleError("ab3456789012".slice(0, 11), "", HOSTED),
    "Password must be at least 12 characters and include at least 2 letters.");
  assert.equal(passwordRuleError("ab3456789012", "", HOSTED), null);
});

test("hosted rule: a password containing the username is refused", () => {
  assert.equal(passwordRuleError("my-ZZTESTJuliet-77", "ZZTEST Juliet", HOSTED), PASSWORD_HAS_USERNAME_MESSAGE);
  assert.equal(passwordRuleError("juliet-garden-77", "ZZTEST Juliet", HOSTED), PASSWORD_HAS_USERNAME_MESSAGE);
  assert.equal(passwordRuleError("quiet-garden-77", "ZZTEST Juliet", HOSTED), null);
});

test("username matching: whole name without spaces (3+) or a word of 4+ letters", () => {
  assert.equal(containsUsername("xxaaronjamesxx", "Aaron James"), true);
  assert.equal(containsUsername("xxJAMESxx", "Aaron James"), true);
  assert.equal(containsUsername("xxbobxx", "Bo b"), true);         // whole name "bob" (3+)
  assert.equal(containsUsername("bo-garden-1", "Bo b"), false);    // words under 4 letters don't count alone
  assert.equal(containsUsername("anything", ""), false);
});
