import { LinkButton } from "../components/ui";
import { useI18n } from "../i18n";

export default function NotFound() {
  const { t } = useI18n();
  return (
    <div className="flex flex-col items-center py-24 text-center">
      <div className="num text-6xl font-bold text-slate-200">404</div>
      <h1 className="mt-4 text-xl font-semibold text-slate-800">{t.notFound.title}</h1>
      <LinkButton to="/" className="mt-6">
        {t.notFound.back}
      </LinkButton>
    </div>
  );
}
