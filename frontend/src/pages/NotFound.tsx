import { Mascot } from "../components/Mascot";
import { LinkButton } from "../components/ui";
import { useI18n } from "../i18n";

export default function NotFound() {
  const { t, f } = useI18n();
  return (
    <div className="animate-pop-in flex flex-col items-center py-20 text-center sm:py-28">
      <Mascot pose="busy" className="w-32" />
      <div className="num mt-6 text-7xl font-black text-brand-600/15 sm:text-8xl">{f.num(404)}</div>
      <h1 className="mt-2 text-2xl font-extrabold text-ink-950">{t.notFound.title}</h1>
      <p className="mt-2 max-w-sm text-[15px] leading-7 text-slate-500">{t.panel.notFound.hint}</p>
      <LinkButton to="/" size="lg" className="mt-8">
        {t.notFound.back}
      </LinkButton>
    </div>
  );
}
