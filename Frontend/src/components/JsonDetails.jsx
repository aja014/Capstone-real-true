import {
  labelFor, orderedEntries, isEmptyValue, formatRating, formatPeso, formatPlain, RATING_STYLE,
} from "../lib/viewFormat";

// Body of the View popup for one stored JSON field (Survey Report's five, Quotation's
// Conditions). Labels and formats come from lib/viewFormat.js; values are the stored ones.

const Dash = () => <span className="text-gray-400">—</span>;

function Rows({ children }) {
  return <table className="w-full text-xs text-gray-700"><tbody>{children}</tbody></table>;
}

function Occupancy({ value }) {
  return (
    <Rows>
      {orderedEntries("occupancy_breakdown", value).map(([k, v]) => {
        const total = k === "total";
        return (
          <tr key={k} className={total ? "border-t border-gray-300 font-bold" : "border-b border-gray-100"}>
            <td className="py-1.5 pr-3">{labelFor("occupancy_breakdown", k)}</td>
            <td className="py-1.5 text-right whitespace-nowrap">{isEmptyValue(v) ? <Dash /> : formatPeso(v)}</td>
          </tr>
        );
      })}
    </Rows>
  );
}

function Boundaries({ value }) {
  return (
    <Rows>
      {orderedEntries("boundaries", value).map(([k, v]) => (
        <tr key={k} className="border-b border-gray-100">
          <td className="py-1.5 pr-3 font-semibold w-24 align-top">{labelFor("boundaries", k)}</td>
          <td className="py-1.5">{isEmptyValue(v) ? <Dash /> : formatPlain(v)}</td>
        </tr>
      ))}
    </Rows>
  );
}

// Perils / Hazard Assessment: { key: { rating, remarks } }.
function Ratings({ field, value, itemHeader }) {
  return (
    <table className="w-full text-xs text-gray-700">
      <thead>
        <tr className="border-b border-gray-200 text-left">
          <th className="py-1.5 pr-3 font-bold">{itemHeader}</th>
          <th className="py-1.5 pr-3 font-bold">Rating</th>
          <th className="py-1.5 font-bold">Remarks</th>
        </tr>
      </thead>
      <tbody>
        {orderedEntries(field, value).map(([k, v]) => {
          const entry = v && typeof v === "object" ? v : { rating: v };
          const rating = formatRating(entry.rating);
          return (
            <tr key={k} className="border-b border-gray-100">
              <td className="py-1.5 pr-3">{labelFor(field, k)}</td>
              <td className={`py-1.5 pr-3 font-semibold ${RATING_STYLE[rating] || ""}`}>
                {rating === "—" ? <Dash /> : rating}
              </td>
              <td className="py-1.5">{isEmptyValue(entry.remarks) ? <Dash /> : formatPlain(entry.remarks)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function Facilities({ value }) {
  return (
    <div className="grid grid-cols-2 gap-x-4 text-xs text-gray-700">
      {orderedEntries("protection_facilities", value).map(([k, v]) => (
        <div key={k} className="flex items-center justify-between gap-2 py-1.5 border-b border-gray-100">
          <span>{labelFor("protection_facilities", k)}</span>
          {v === true ? <span className="text-green-600 font-bold" aria-label="Yes">✓</span>
            : v === false ? <span className="text-gray-400 font-bold" aria-label="No">✗</span>
            : isEmptyValue(v) ? <Dash /> : <span>{formatPlain(v)}</span>}
        </div>
      ))}
    </div>
  );
}

// Any other shape (Conditions): labelled list, nested objects indented.
function Generic({ field, value }) {
  if (Array.isArray(value)) {
    return (
      <ul className="list-disc pl-4 text-xs text-gray-700">
        {value.map((v, i) => (
          <li key={i} className="py-0.5">
            {v && typeof v === "object" ? <Generic field={field} value={v} /> : formatPlain(v)}
          </li>
        ))}
      </ul>
    );
  }
  if (!value || typeof value !== "object") {
    return <span className="text-xs text-gray-700">{isEmptyValue(value) ? <Dash /> : formatPlain(value)}</span>;
  }
  return (
    <dl className="text-xs text-gray-700">
      {Object.entries(value).map(([k, v]) => (
        <div key={k} className="py-1.5 border-b border-gray-100">
          <dt className="font-semibold">{labelFor(field, k)}</dt>
          <dd className="mt-0.5 whitespace-pre-wrap break-words">
            {v && typeof v === "object"
              ? <div className="pl-3"><Generic field={field} value={v} /></div>
              : isEmptyValue(v) ? <Dash /> : formatPlain(v)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export default function JsonDetails({ field, value }) {
  const isObject = value && typeof value === "object" && !Array.isArray(value);
  if (isObject && field === "occupancy_breakdown") return <Occupancy value={value} />;
  if (isObject && field === "boundaries") return <Boundaries value={value} />;
  if (isObject && field === "perils_assessment") return <Ratings field={field} value={value} itemHeader="Peril" />;
  if (isObject && field === "hazard_assessment") return <Ratings field={field} value={value} itemHeader="Hazard" />;
  if (isObject && field === "protection_facilities") return <Facilities value={value} />;
  return <Generic field={field} value={value} />;
}
