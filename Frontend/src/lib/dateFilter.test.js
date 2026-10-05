import { test } from "node:test";
import assert from "node:assert/strict";
import { matchesPickedDate, extractDateParts } from "./dateFilter.js";

const picked = new Date(2025, 2, 7); // local 03/07/2025, as the calendar gives it

test("no date picked: every row, also rows without a date", () => {
  assert.equal(matchesPickedDate(null, null), true);
  assert.equal(matchesPickedDate("2025-03-07", null), true);
});

test("date picked: a row with no or an unreadable date is hidden", () => {
  assert.equal(matchesPickedDate(null, picked), false);
  assert.equal(matchesPickedDate("", picked), false);
  assert.equal(matchesPickedDate("not a date", picked), false);
});

test("date picked: rows with that day match in every stored form", () => {
  assert.equal(matchesPickedDate("2025-03-07", picked), true);
  assert.equal(matchesPickedDate("2025-03-07T06:30:00", picked), true); // before 08:00 stays the same day
  assert.equal(matchesPickedDate("03/07/2025", picked), true);
});

test("date picked: other days do not match", () => {
  assert.equal(matchesPickedDate("2025-03-06", picked), false);
  assert.equal(matchesPickedDate("2025-03-08", picked), false);
  assert.equal(matchesPickedDate("2024-03-07", picked), false);
});

test("extractDateParts reads ISO and MM/DD/YYYY alike", () => {
  assert.deepEqual(extractDateParts("2025-03-07"), { month: 3, day: 7, year: 2025 });
  assert.deepEqual(extractDateParts("03/07/2025"), { month: 3, day: 7, year: 2025 });
  assert.equal(extractDateParts(null), null);
});
