import { formatPercent, formatTrainedDate } from "../lib/ml";

// Risk Assessment = the Logistic Regression risk level. Low / Medium / High are set
// per line from its training loss rate (see the model report); "—" = no prediction
// (the quotation's policy has already ended, or no model is trained yet).
const RISK_STYLE = {
  Low: "text-gray-600",
  Medium: "text-amber-600 font-semibold",
  High: "text-red-500 font-semibold",
};

export function RiskLevelCell({ value }) {
  if (!value) return <span className="text-gray-400">—</span>;
  return <span className={RISK_STYLE[value] || ""}>{value}</span>;
}

// Claim Possibility = the model's predicted probability of a counted loss.
export function ClaimPossibilityCell({ value }) {
  if (value === null || value === undefined) return <span className="text-gray-400">—</span>;
  return <span>{formatPercent(value)}</span>;
}

// Small "how good is the model" card: the 5-fold cross-validation AVERAGES (every row
// is tested once), not the single 25% test split -- those test sets are small (the fraud
// one has ~12 fraud cases), so one split's score swings a lot. Both are in the report.
// Recall is worded as "catches X% of <positives>": accuracy alone looks high even for
// a model that predicts nothing. AUC (how well the model ranks risky above safe, 0.5 =
// guessing) doesn't depend on any cutoff.
// rows: [{ label, model, positives }], model = one GET /ml/models summary (undefined
// while loading or if the request failed).
const formatAuc = (v) => (v === null || v === undefined ? "—" : v.toFixed(2));

export function ModelAccuracyCard({ title, rows, loading }) {
  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm flex flex-col gap-3">
      <div>
        <p className="text-black font-bold text-sm">{title}</p>
        <p className="text-gray-400 text-[10px]">5-fold average (cross-validation)</p>
      </div>
      {rows.map(({ label, model, positives }) => (
        <div key={label} className="flex flex-col gap-0.5">
          <p className="text-gray-500 text-[10px] font-semibold">{label}</p>
          {loading ? (
            <p className="text-gray-400 text-xs">…</p>
          ) : !model?.available ? (
            <p className="text-gray-400 text-xs">Not trained yet</p>
          ) : (
            <>
              <p className="text-black text-xs">
                <span className="font-black text-2xl leading-none">
                  {formatPercent(model.cross_validation?.accuracy?.mean)}
                </span>
                <span className="text-gray-600"> accurate</span>
              </p>
              <p className="text-gray-600 text-xs">
                catches {formatPercent(model.cross_validation?.recall?.mean)} of {positives}
              </p>
              <p className="text-gray-600 text-xs">
                AUC {formatAuc(model.cross_validation?.roc_auc?.mean)} (0.5 = guessing)
              </p>
              <p className="text-gray-400 text-[10px]">
                v{model.version} · trained {formatTrainedDate(model.trained_at)}
              </p>
            </>
          )}
        </div>
      ))}
    </div>
  );
}
