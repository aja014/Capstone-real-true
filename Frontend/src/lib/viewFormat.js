// View popups (Policy Holder Information → Survey Report / Quotation): readable labels and
// display forms for the stored JSON fields. Display only — the stored values are unchanged.
//
// Labels are the real form wording already used by the upload (the Survey Report column
// headers, Backend/app/routers/import_fire_property.py, and PROTECTION_FACILITY_OPTIONS in
// Backend/app/schemas.py). Where the form only has an abbreviation, the meaning follows it
// in brackets. The map order is the form order.
export const VIEW_LABELS = {
  occupancy_breakdown: {
    building: "Building",
    main_occupancy: "Main Occupancy",
    stocks: "Stocks",
    me: "M/E (Machinery & Equipment)",
    fff: "FFF (Furniture, Fixtures & Fittings)",
    bi_lop: "BI/LOP (Business Interruption / Loss of Profit)",
    others: "Others",
    total: "Total",
  },
  boundaries: {
    front: "Front",
    right: "Right",
    left: "Left",
    rear: "Rear",
    sketch: "Sketch",
  },
  perils_assessment: {
    fire: "Fire",
    earthquake: "Earthquake",
    typhoon: "Typhoon",
    flood: "Flood",
    burglary_robbery: "Burglary/Robbery",
    rsmd: "RSMD (Riot, Strike & Malicious Damage)",
    landslide_subsidence: "Landslide/Subsidence",
    smoke_aircraft_vehicle_impact_explosion: "Smoke/Aircraft/Vehicle Impact/Explosion",
    volcanic_eruption: "Volcanic Eruption",
    tsunami: "Tsunami",
    terrorist_attack: "Terrorist Attack",
    spontaneous_combustion: "Spontaneous Combustion",
    machinery_breakdown: "Machinery Breakdown",
    general_liability: "General Liability",
    money: "Money",
    fidelity_guarantee: "Fidelity Guarantee",
    goods_transit: "Goods Transit",
    others: "Others",
  },
  hazard_assessment: {
    maintenance: "Maintenance",
    housekeeping: "Housekeeping",
    storage_arrangement: "Storage Arrangement",
    safety_security: "Safety/Security",
    block_condition: "Block Condition",
    surrounding_community: "Surrounding Community",
  },
  protection_facilities: {
    risk_management_units: "Risk Management/Safety/Security Units",
    plant_safety: "Plant Safety",
    flood_control: "Flood Control",
    security_control: "Security Control",
    access_to_site: "Access to Plant/Site",
    sprinklers: "Automatic Sprinklers",
    internal_hydrants: "Internal Hydrants",
    external_hydrants: "External Hydrants",
    fire_alarm: "Fire Alarm System",
    smoke_detector: "Smoke Detector",
    heat_detector: "Heat Detector",
    fire_extinguisher: "Fire Extinguisher",
    fire_brigade: "Fire Brigade",
    fire_breaks_doors: "Fire Breaks/Doors",
    fire_truck: "Fire Truck",
    fire_pump: "Fire Pump",
    jockey_pump: "Jockey Pump",
    public_private_fire_fighting: "Public/Private Fire Fighting",
    security_guards: "Security Guards",
    hot_works_permit: "Hot Works Permit",
    water_supply: "Water Supply",
    power_supply: "Power Supply",
    generator_set: "Generator Set",
    telecommunications: "Telecommunications",
    cctv: "CCTV/Monitor/Recording",
    sniffing_dogs: "Sniffing Dogs",
    metal_detectors_frisking: "Metal Detectors/Frisking",
    fire_fighting_appliances_inspection: "Fire Fighting Appliances Inspection",
    perimeter_fence: "Perimeter Fence",
    police_armed_force: "Police/Armed Force",
    redundancies_bcp_drp: "Redundancies/BCP/DRP",
    others: "Others",
  },
};

// A key with no form wording (e.g. a Conditions entry): "general_conditions" → "General Conditions".
export function humanizeKey(key) {
  return String(key).split("_").filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
}

export function labelFor(field, key) {
  return VIEW_LABELS[field]?.[key] ?? humanizeKey(key);
}

// [key, value] pairs: every form item in form order (missing ones get undefined → "—"),
// then any stored key the form doesn't list, so nothing stored is ever hidden.
export function orderedEntries(field, obj) {
  const known = Object.keys(VIEW_LABELS[field] ?? {});
  const extra = Object.keys(obj ?? {}).filter((k) => !known.includes(k));
  return [...known, ...extra].map((k) => [k, obj?.[k]]);
}

export function isEmptyValue(v) {
  return v === null || v === undefined || (typeof v === "string" && v.trim() === "");
}

// "moderate" → "Moderate"; empty → "—".
export function formatRating(v) {
  if (isEmptyValue(v)) return "—";
  return String(v).toLowerCase().replace(/\b[a-z]/g, (c) => c.toUpperCase());
}

// Same colours as the Flood Risk View (FloodRiskModal.jsx): good → green, middle → amber, bad → red.
export const RATING_STYLE = {
  Low: "text-green-600",
  Moderate: "text-amber-600",
  High: "text-red-600",
  Good: "text-green-600",
  Fair: "text-amber-600",
  Poor: "text-red-600",
};

// ₱1,234.56 like the table cells; empty → "—"; a non-number is shown as stored.
export function formatPeso(v) {
  if (isEmptyValue(v)) return "—";
  const n = Number(v);
  if (isNaN(n)) return String(v);
  return `₱${n.toLocaleString("en-PH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

// Plain text value: empty → "—", true/false → ✓ / ✗, otherwise as stored.
export function formatPlain(v) {
  if (isEmptyValue(v)) return "—";
  if (typeof v === "boolean") return v ? "✓" : "✗";
  return String(v);
}
