import { useState } from "react";
import { Link } from "react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, BellRing, Check } from "lucide-react";
import { api } from "../api/client";
import { keys, useDashboard, useMe } from "../api/queries";
import type { Shop } from "../api/types";
import { useToast } from "../components/toast";
import { Alert, Card, ConfirmDialog, LinkButton, PageHeader, PageLoading, Toggle, cx } from "../components/ui";
import { useI18n } from "../i18n";
import { errorMessage } from "../lib/errors";
import { getFlag, playgroundKey } from "../lib/storage";

export default function Dashboard() {
  const { t, f } = useI18n();
  const toast = useToast();
  const qc = useQueryClient();
  const { data, isPending, error, refetch } = useDashboard();
  const { data: me } = useMe();
  const [confirmOn, setConfirmOn] = useState(false);

  const toggleBot = useMutation({
    mutationFn: (enabled: boolean) => api<Shop>("/shop", { method: "PATCH", json: { bot_enabled: enabled } }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.dashboard });
      qc.invalidateQueries({ queryKey: keys.shop });
      qc.invalidateQueries({ queryKey: keys.me });
      setConfirmOn(false);
    },
    onError: (err) => toast.error(errorMessage(err, t)),
  });

  if (isPending) return <PageLoading />;
  if (error) return <Alert kind="error" action={<button onClick={() => refetch()} className="underline">{t.common.retry}</button>}>{errorMessage(error, t)}</Alert>;

  const s = data.setup;
  const igOk = s.instagram_connected && s.instagram_active;
  const tried = me ? getFlag(playgroundKey(me.shop.id)) : false;

  const steps: { done: boolean; title: string; hint: string; to?: string; optional?: boolean }[] = [
    { done: igOk, title: t.dashboard.stepInstagram, hint: t.dashboard.stepInstagramHint, to: "/instagram" },
    { done: s.knowledge_entries > 0, title: t.dashboard.stepKnowledge, hint: t.dashboard.stepKnowledgeHint, to: "/knowledge" },
    { done: s.products_connected, title: t.dashboard.stepProducts, hint: t.dashboard.stepProductsHint, to: "/products", optional: true },
    { done: tried, title: t.dashboard.stepPlayground, hint: t.dashboard.stepPlaygroundHint, to: "/playground" },
    { done: s.bot_enabled, title: t.dashboard.stepBot, hint: t.dashboard.stepBotHint },
  ];
  const doneCount = steps.filter((x) => x.done).length;
  // the optional products step doesn't keep the checklist on screen
  const allDone = steps.every((x) => x.done || x.optional);

  const stats = data.last_7_days;
  const hasActivity = stats.conversations + stats.customer_messages + stats.bot_replies > 0;

  function setBot(on: boolean) {
    if (on && (!igOk || s.knowledge_entries === 0)) setConfirmOn(true);
    else toggleBot.mutate(on);
  }

  return (
    <div className="space-y-6">
      <PageHeader title={t.dashboard.title} />

      {data.open_handoffs > 0 && (
        <Link
          to="/handoffs"
          className="flex flex-wrap items-center gap-4 rounded-xl bg-red-600 p-5 text-white shadow-md transition hover:bg-red-700"
        >
          <span className="rounded-full bg-white/15 p-3">
            <BellRing className="size-6" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="text-lg font-bold">{t.dashboard.waitingCard(f.num(data.open_handoffs))}</div>
            <div className="text-sm text-red-100">{t.dashboard.waitingCardHint}</div>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-lg bg-white px-4 py-2 text-sm font-semibold text-red-700">
            {t.dashboard.waitingCardAction}
            <ArrowLeft className="size-4 ltr:rotate-180" />
          </span>
        </Link>
      )}

      {s.instagram_connected && !s.instagram_active && (
        <Alert kind="warning" action={<LinkButton to="/instagram" size="sm" variant="secondary">{t.dashboard.alertIgInactiveAction}</LinkButton>}>
          {t.dashboard.alertIgInactive}
        </Alert>
      )}
      {s.product_error && (
        <Alert kind="warning" action={<LinkButton to="/products" size="sm" variant="secondary">{t.dashboard.alertProductsAction}</LinkButton>}>
          {s.product_error}
        </Alert>
      )}
      {!s.ai_ready && <Alert kind="info">{t.dashboard.alertAi}</Alert>}

      <Card className="flex flex-wrap items-center gap-4 p-5">
        <span className={cx("size-3 rounded-full", s.bot_enabled ? "bg-emerald-500 ring-4 ring-emerald-100" : "bg-slate-300 ring-4 ring-slate-100")} />
        <div className="min-w-0 flex-1">
          <div className="text-sm text-slate-500">{t.dashboard.botStatus}</div>
          <div className="font-semibold text-slate-900">{s.bot_enabled ? t.dashboard.botOn : t.dashboard.botOff}</div>
          {s.instagram_username && <div className="ltr mt-0.5 text-xs text-slate-500">@{s.instagram_username}</div>}
        </div>
        <Toggle checked={s.bot_enabled} onChange={setBot} disabled={toggleBot.isPending} label={t.dashboard.botStatus} />
      </Card>

      {!allDone && (
        <Card>
          <div className="border-b border-slate-100 px-5 py-4">
            <div className="flex items-center justify-between gap-3">
              <h2 className="font-semibold text-slate-900">{t.dashboard.checklistTitle}</h2>
              <span className="text-sm text-slate-500">{t.dashboard.checklistProgress(f.num(doneCount), f.num(steps.length))}</span>
            </div>
            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-emerald-500 transition-all" style={{ width: `${(doneCount / steps.length) * 100}%` }} />
            </div>
          </div>
          <ol className="divide-y divide-slate-100">
            {steps.map((step, i) => (
              <li key={step.title} className="flex items-center gap-4 px-5 py-4">
                {step.done ? (
                  <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-white">
                    <Check className="size-4" />
                  </span>
                ) : (
                  <span className="num flex size-7 shrink-0 items-center justify-center rounded-full border-2 border-slate-200 text-sm font-semibold text-slate-400">
                    {f.num(i + 1)}
                  </span>
                )}
                <div className="min-w-0 flex-1">
                  <div className={cx("font-medium", step.done ? "text-slate-400 line-through" : "text-slate-900")}>
                    {step.title}
                    {step.optional && <span className="ms-1.5 text-xs font-normal text-slate-400">({t.common.optional})</span>}
                  </div>
                  {!step.done && <div className="text-sm text-slate-500">{step.hint}</div>}
                </div>
                {!step.done &&
                  (step.to ? (
                    <LinkButton to={step.to} size="sm" variant="soft">
                      {t.dashboard.doStep}
                    </LinkButton>
                  ) : (
                    <Toggle checked={s.bot_enabled} onChange={setBot} disabled={toggleBot.isPending} label={step.title} />
                  ))}
              </li>
            ))}
          </ol>
        </Card>
      )}

      {/* A brand-new shop sees only the checklist, not a wall of zeros. */}
      {(allDone || hasActivity) && (
        <section>
          <h2 className="mb-3 text-sm font-semibold text-slate-500">{t.dashboard.last7Days}</h2>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label={t.dashboard.statConversations} value={f.num(stats.conversations)} />
            <Stat label={t.dashboard.statCustomerMessages} value={f.num(stats.customer_messages)} />
            <Stat label={t.dashboard.statBotReplies} value={f.num(stats.bot_replies)} />
            <Stat label={t.dashboard.statOpenUnanswered} value={f.num(stats.open_unanswered)} to="/unanswered" warn={stats.open_unanswered > 0} />
          </div>
          <p className="mt-4 text-xs text-slate-400">
            {t.dashboard.tokensThisMonth}: <span className="num">{f.num(data.tokens_this_month)}</span> {t.dashboard.tokensUnit}
          </p>
        </section>
      )}

      <ConfirmDialog
        open={confirmOn}
        onClose={() => setConfirmOn(false)}
        onConfirm={() => toggleBot.mutate(true)}
        loading={toggleBot.isPending}
        title={t.dashboard.botTurnOnConfirmTitle}
        body={
          <ul className="list-disc space-y-1 ps-5">
            {!igOk && <li>{t.dashboard.botTurnOnConfirmIg}</li>}
            {s.knowledge_entries === 0 && <li>{t.dashboard.botTurnOnConfirmKnowledge}</li>}
          </ul>
        }
        confirmLabel={t.dashboard.botTurnOnAnyway}
        cancelLabel={t.common.cancel}
      />
    </div>
  );
}

function Stat({ label, value, to, warn }: { label: string; value: string; to?: string; warn?: boolean }) {
  const body = (
    <>
      <div className="text-sm text-slate-500">{label}</div>
      <div className={cx("num mt-1 text-2xl font-bold", warn ? "text-amber-600" : "text-slate-900")}>{value}</div>
    </>
  );
  const cls = "block rounded-xl border border-slate-200 bg-white p-4 shadow-sm";
  return to ? (
    <Link to={to} className={cx(cls, "transition hover:border-brand-200")}>
      {body}
    </Link>
  ) : (
    <div className={cls}>{body}</div>
  );
}
