const TZ = "Asia/Karachi";

export const fmtTime = (iso) =>
  iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", timeZone: TZ }) : "—";

export const fmtDateTime = (iso) =>
  iso ? new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short", timeZone: TZ }) : "—";

export const fmtDate = (d) => (d ? new Date(d + "T00:00:00").toLocaleDateString([], { dateStyle: "medium" }) : "—");

export const hhmm = (t) => (t ? t.slice(0, 5) : "");

export const fmtMinutes = (m) => (m == null ? "—" : `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, "0")}m`);

export const todayStr = () => new Date().toLocaleDateString("en-CA", { timeZone: TZ });

export const addDays = (dateStr, n) => {
  const d = new Date(dateStr + "T00:00:00");
  d.setDate(d.getDate() + n);
  return d.toLocaleDateString("en-CA");
};

export const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export const label = (s) => (s ? s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) : "");

/** value for <input type="datetime-local"> from an ISO instant, in company time */
export const toLocalInput = (iso) => {
  if (!iso) return "";
  const p = new Intl.DateTimeFormat("en-CA", {
    timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).formatToParts(new Date(iso)).reduce((o, x) => ({ ...o, [x.type]: x.value }), {});
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
};

/** ISO instant from a datetime-local value interpreted in company time (UTC+5, no DST) */
export const fromLocalInput = (v) => (v ? `${v}:00+05:00` : null);
