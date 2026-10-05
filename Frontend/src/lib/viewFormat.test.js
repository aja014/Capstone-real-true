import { test } from "node:test";
import assert from "node:assert/strict";
import {
  VIEW_LABELS, labelFor, humanizeKey, orderedEntries, formatRating, formatPeso, formatPlain, RATING_STYLE,
} from "./viewFormat.js";

test("labels use the form wording (with the meaning after an abbreviation)", () => {
  assert.equal(labelFor("perils_assessment", "goods_transit"), "Goods Transit");
  assert.equal(labelFor("occupancy_breakdown", "fff"), "FFF (Furniture, Fixtures & Fittings)");
  assert.equal(labelFor("hazard_assessment", "safety_security"), "Safety/Security");
  assert.equal(labelFor("protection_facilities", "cctv"), "CCTV/Monitor/Recording");
});

test("item counts match the Survey Report form", () => {
  assert.equal(Object.keys(VIEW_LABELS.perils_assessment).length, 18);
  assert.equal(Object.keys(VIEW_LABELS.hazard_assessment).length, 6);
  assert.equal(Object.keys(VIEW_LABELS.occupancy_breakdown).length, 8);
  assert.equal(Object.keys(VIEW_LABELS.boundaries).length, 5);
  assert.equal(Object.keys(VIEW_LABELS.protection_facilities).length, 32);
});

test("a key with no form wording gets a readable fallback", () => {
  assert.equal(labelFor("conditions", "general_conditions"), "General Conditions");
  assert.equal(humanizeKey("coinsurance"), "Coinsurance");
});

test("orderedEntries: form order, missing items as undefined, unknown keys kept at the end", () => {
  const entries = orderedEntries("boundaries", { rear: "Chapel", front: "Street", extra_note: "x" });
  assert.deepEqual(entries.map(([k]) => k), ["front", "right", "left", "rear", "sketch", "extra_note"]);
  assert.equal(entries[0][1], "Street");
  assert.equal(entries[1][1], undefined);
});

test("ratings in title case, with the existing colours", () => {
  assert.equal(formatRating("moderate"), "Moderate");
  assert.equal(formatRating("POOR"), "Poor");
  assert.equal(formatRating(null), "—");
  assert.equal(RATING_STYLE.High, "text-red-600");
  assert.equal(RATING_STYLE.Good, "text-green-600");
});

test("amounts as ₱1,234.56; empty as —; values otherwise exactly as stored", () => {
  assert.equal(formatPeso(1005000), "₱1,005,000.00");
  assert.equal(formatPeso("1234.5"), "₱1,234.50");
  assert.equal(formatPeso(null), "—");
  assert.equal(formatPeso("n/a text"), "n/a text");
  assert.equal(formatPlain(true), "✓");
  assert.equal(formatPlain(false), "✗");
  assert.equal(formatPlain(""), "—");
  assert.equal(formatPlain("Barangay road"), "Barangay road");
});
