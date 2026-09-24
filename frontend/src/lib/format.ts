import type { Dict } from "../i18n/fa";

// Dates from the API are UTC ISO strings; shown in the browser's timezone, Jalali for Persian.

export type Format = ReturnType<typeof makeFormat>;

export function makeFormat(lang: "fa" | "en", t: Dict) {
  const locale = lang === "fa" ? "fa-IR" : "en-US";
  const num = new Intl.NumberFormat(locale);
  const dateTime = new Intl.DateTimeFormat(lang === "fa" ? "fa-IR-u-ca-persian" : "en-GB", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
  const date = new Intl.DateTimeFormat(lang === "fa" ? "fa-IR-u-ca-persian" : "en-GB", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
  const time = new Intl.DateTimeFormat(locale, { hour: "2-digit", minute: "2-digit" });
  const shortDay = new Intl.DateTimeFormat(lang === "fa" ? "fa-IR-u-ca-persian" : "en-GB", {
    month: "short",
    day: "numeric",
  });
  const rel = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });

  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 365 * 24 * 3600],
    ["month", 30 * 24 * 3600],
    ["day", 24 * 3600],
    ["hour", 3600],
    ["minute", 60],
  ];

  return {
    /** 1250000 → "۱٬۲۵۰٬۰۰۰" */
    num: (n: number | string | null | undefined) => {
      if (n === null || n === undefined || n === "") return "";
      const v = typeof n === "string" ? Number(n) : n;
      return Number.isFinite(v) ? num.format(v) : String(n);
    },
    dateTime: (iso: string) => dateTime.format(new Date(iso)),
    date: (iso: string) => date.format(new Date(iso)),
    /** Time only if today, else short date + time. */
    smart: (iso: string) => {
      const d = new Date(iso);
      const now = new Date();
      if (d.toDateString() === now.toDateString()) return time.format(d);
      return `${shortDay.format(d)}${lang === "fa" ? "،" : ","} ${time.format(d)}`;
    },
    time: (iso: string) => time.format(new Date(iso)),
    /** "۳ دقیقه پیش" */
    ago: (iso: string, now = Date.now()) => {
      const secs = (new Date(iso).getTime() - now) / 1000;
      for (const [unit, size] of units) {
        if (Math.abs(secs) >= size) return rel.format(Math.round(secs / size), unit);
      }
      return t.time.justNow;
    },
    /** Elapsed time without "ago": "۱۴ دقیقه" / "۲ ساعت" */
    duration: (iso: string, now = Date.now()) => {
      const mins = Math.max(0, Math.floor((now - new Date(iso).getTime()) / 60000));
      const fmt = (value: number, unit: "minute" | "hour" | "day") =>
        new Intl.NumberFormat(locale, { style: "unit", unit, unitDisplay: "long" }).format(value);
      if (mins < 60) return fmt(Math.max(1, mins), "minute");
      if (mins < 60 * 24) return fmt(Math.floor(mins / 60), "hour");
      return fmt(Math.floor(mins / 1440), "day");
    },
  };
}

/** Display name for a customer: username, or "Customer 0001" from the Instagram ID. */
export function customerName(username: string | null | undefined, igsid: string, t: Dict, f: Format): string {
  if (username) return username;
  return `${t.common.customer} ${toLocaleDigits(igsid.slice(-4), f)}`;
}

function toLocaleDigits(digits: string, f: Format): string {
  return digits.replace(/\d/g, (d) => f.num(Number(d)));
}

export function formatBytesMB(bytes: number): string {
  return String(Math.round((bytes / 1024 / 1024) * 10) / 10);
}
