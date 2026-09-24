import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import en from "./en";
import fa, { type Dict } from "./fa";
import { makeFormat, type Format } from "../lib/format";

export type Lang = "fa" | "en";

const dicts: Record<Lang, Dict> = { fa, en };
const STORAGE_KEY = "dm.lang";

type I18n = { lang: Lang; dir: "rtl" | "ltr"; t: Dict; f: Format; setLang: (l: Lang) => void; toggleLang: () => void };

const I18nContext = createContext<I18n | null>(null);

function initialLang(): Lang {
  const fromUrl = new URLSearchParams(location.search).get("lang");
  if (fromUrl === "en" || fromUrl === "fa") return fromUrl;
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "en" || saved === "fa") return saved;
  } catch {
    // storage unavailable
  }
  return "fa";
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang);
  const dir = lang === "fa" ? "rtl" : "ltr";

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = dir;
  }, [lang, dir]);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem(STORAGE_KEY, l);
    } catch {
      // storage unavailable
    }
  }, []);

  const value = useMemo<I18n>(
    () => ({
      lang,
      dir,
      t: dicts[lang],
      f: makeFormat(lang, dicts[lang]),
      setLang,
      toggleLang: () => setLang(lang === "fa" ? "en" : "fa"),
    }),
    [lang, dir, setLang],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18n {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n outside I18nProvider");
  return ctx;
}
