-- Fire policy: "Unit Cost Premium" wrongly merged the form's separate Unit Cost and Premium
-- columns. It becomes premium = the policy's Total Premium in pesos, before taxes.
-- Maagap's real fire policy: Total Amount Due = Total Premium x 1.27
-- (Doc. Stamps 12.5% + FST 2% + VAT 12% + Local Gov't Tax 0.5%), so current rows get
-- premium = Total Amount Due / 1.27 until the Oct 12 load.
-- deleted_fire_property_policies has no columns to rename (JSON snapshots; 0 rows in v4).
-- Run once, after a full mysqldump backup (2026-10-05, branch premium-field).
ALTER TABLE fire_property_policies RENAME COLUMN unit_cost_premium TO premium;
UPDATE fire_property_policies SET premium = ROUND(total_amount_due / 1.27, 2) WHERE total_amount_due IS NOT NULL;
