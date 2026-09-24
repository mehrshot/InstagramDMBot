import type { ReactNode } from "react";
import { Link } from "react-router";
import { Languages } from "lucide-react";
import { useI18n } from "../i18n";

export default function AuthShell({ title, subtitle, children, footer }: { title: string; subtitle: string; children: ReactNode; footer: ReactNode }) {
  const { t, toggleLang } = useI18n();
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-b from-brand-50 to-slate-50 px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center text-center">
          <img src="/favicon.svg" alt="" className="mb-3 size-12" />
          <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
          <p className="mt-1 text-sm text-slate-500">{subtitle}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">{children}</div>
        <p className="mt-5 text-center text-sm text-slate-600">{footer}</p>
        <div className="mt-8 flex items-center justify-center gap-4 text-xs text-slate-400">
          <button type="button" onClick={toggleLang} className="inline-flex items-center gap-1 hover:text-slate-600">
            <Languages className="size-3.5" />
            {t.otherLang}
          </button>
          <Link to="/privacy" className="hover:text-slate-600">
            {t.legal.privacy}
          </Link>
          <Link to="/terms" className="hover:text-slate-600">
            {t.legal.terms}
          </Link>
        </div>
      </div>
    </div>
  );
}
