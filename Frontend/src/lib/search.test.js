import { test } from "node:test";
import assert from "node:assert/strict";
import { rowMatchesSearch, fieldsMatchSearch, searchWords } from "./search.js";

// A fresh object per call: rowMatchesSearch caches each row's text by object.
const client = () => ({ id: 1, last_name: "Umali", first_name: "Antonio", middle_name: "Gonzales", mobile_number: null });

test("full name across Last/First/Middle Name columns matches (TC_CLIENT_002)", () => {
  assert.equal(rowMatchesSearch(client(), "Antonio Gonzales Umali"), true);
  assert.equal(rowMatchesSearch(client(), "Gonzales Umali"), true);
});

test("word order and case do not matter; extra spaces are ignored", () => {
  assert.equal(rowMatchesSearch(client(), "  umali   ANTONIO "), true);
});

test("every word must appear somewhere", () => {
  assert.equal(rowMatchesSearch(client(), "Antonio Reyes"), false);
});

test("one word behaves as a plain substring search", () => {
  assert.equal(rowMatchesSearch(client(), "mal"), true);
  assert.equal(rowMatchesSearch(client(), "null"), false); // empty fields add nothing
  assert.equal(rowMatchesSearch(client(), ""), true);
  assert.equal(rowMatchesSearch(client(), "   "), true);
});

test("a word never spans two fields", () => {
  assert.equal(rowMatchesSearch(client(), "UmaliAntonio"), false);
});

test("dates (MM/DD/YYYY) and money (₱1,234.56) still match, also mixed with a name", () => {
  const policy = () => ({
    policy_no: "MS-01-22-MS-000001", issue_date: "2022-01-15", total_amount_due: "12345.5",
    client_name: "Antonio Gonzales Umali",
  });
  const money = { total_amount_due: "currency" };
  assert.equal(rowMatchesSearch(policy(), "01/15/2022", money), true);
  assert.equal(rowMatchesSearch(policy(), "₱12,345.50", money), true);
  assert.equal(rowMatchesSearch(policy(), "umali 01/15/2022", money), true);
  assert.equal(rowMatchesSearch(policy(), "MS-01-22-MS-000001", money), true);
});

test("fieldsMatchSearch: same word rule over the given fields only", () => {
  const values = ["MS2602030016", "Antonio Gonzales Umali", null];
  assert.equal(fieldsMatchSearch(values, "umali antonio"), true);
  assert.equal(fieldsMatchSearch(values, "MS2602030016 umali"), true);
  assert.equal(fieldsMatchSearch(values, "umali reyes"), false);
  assert.equal(fieldsMatchSearch(values, "null"), false);
  assert.equal(fieldsMatchSearch(values, ""), true);
});

test("searchWords splits on any whitespace", () => {
  assert.deepEqual(searchWords("  Gonzales \t Umali "), ["gonzales", "umali"]);
  assert.deepEqual(searchWords(""), []);
});
