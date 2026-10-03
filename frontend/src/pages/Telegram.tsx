import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BriefcaseBusiness, Megaphone, Send } from "lucide-react";
import { api } from "../api/client";
import { keys } from "../api/queries";
import type { TelegramStatus } from "../api/types";
import { CustomBot, EnabledCard, Locked, OwnerLink, ShopLink } from "../components/messenger";
import { useToast } from "../components/toast";
import { Alert, Badge, Button, Card, CardHeader, PageHeader, PageLoading } from "../components/ui";
import { useI18n } from "../i18n";
import { errorMessage } from "../lib/errors";

export default function Telegram() {
  const { t } = useI18n();
  const T = t.launch.telegram;
  const qc = useQueryClient();
  const status = useQuery({ queryKey: keys.telegram, queryFn: () => api<TelegramStatus>("/telegram") });

  const refresh = (data?: unknown) => {
    if (data) qc.setQueryData(keys.telegram, data);
    else qc.invalidateQueries({ queryKey: keys.telegram });
    qc.invalidateQueries({ queryKey: keys.dashboard });
  };

  const header = <PageHeader icon={<Send />} title={T.title} subtitle={T.subtitle} />;
  if (status.isPending)
    return (
      <>
        {header}
        <PageLoading />
      </>
    );
  if (status.error)
    return (
      <>
        {header}
        <Alert kind="error">{errorMessage(status.error, t)}</Alert>
      </>
    );

  const s = status.data;
  if (!s.available)
    return (
      <>
        {header}
        <Alert kind="warning">{T.notReady}</Alert>
      </>
    );

  return (
    <div className="max-w-4xl space-y-6">
      {header}
      <EnabledCard platform="telegram" status={s} onChange={refresh} />
      <ShopLink platform="telegram" status={s} />
      <OwnerLink platform="telegram" status={s} onChange={refresh} />
      <Channels status={s} />
      <CustomBot platform="telegram" status={s} onChange={refresh} />
      <Business status={s} onChange={refresh} />
    </div>
  );
}

function Channels({ status }: { status: TelegramStatus }) {
  const { t } = useI18n();
  const T = t.launch.telegram;
  return (
    <Card>
      <CardHeader icon={<Megaphone />} title={T.channelTitle} subtitle={T.channelHint(status.shared_bot_username ?? "")} />
      <div className="space-y-3 p-5 sm:px-6">
        {status.admins.length === 0 && <Alert kind="info">{T.channelNeedsLink}</Alert>}
        {status.channels.length === 0 ? (
          <p className="text-sm text-slate-500">{T.noChannels}</p>
        ) : (
          <ul className="space-y-2">
            {status.channels.map((c) => (
              <li key={c.id} className="flex items-center gap-3 rounded-xl bg-fill px-3.5 py-2.5 text-sm">
                <Megaphone className="size-4 text-slate-400" aria-hidden />
                <span className="min-w-0 flex-1 truncate font-semibold text-ink-900">{c.title}</span>
                {c.username && (
                  <a href={`https://t.me/${c.username}`} target="_blank" rel="noopener noreferrer" dir="ltr" className="text-brand-700 hover:underline">
                    @{c.username}
                  </a>
                )}
                <Badge tone={c.active ? "green" : "neutral"}>{c.active ? T.channelActive : T.channelInactive}</Badge>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}

function Business({ status, onChange }: { status: TelegramStatus; onChange: () => void }) {
  const { t } = useI18n();
  const T = t.launch.telegram;
  const toast = useToast();
  const stop = useMutation({
    mutationFn: () => api("/telegram/business", { method: "DELETE" }),
    onSuccess: () => onChange(),
    onError: (err) => toast.error(errorMessage(err, t)),
  });
  const b = status.business;
  return (
    <Card>
      <CardHeader icon={<BriefcaseBusiness />} title={T.businessTitle} subtitle={T.businessHint} />
      <div className="space-y-4 p-5 sm:px-6">
        {!status.business_allowed && <Locked plan={T.planBusiness} />}
        {b.connected && (
          <div className="flex flex-wrap items-center gap-3">
            <Badge tone={b.enabled ? "green" : "neutral"}>{b.enabled ? T.businessConnected : T.businessDisabled}</Badge>
            {b.enabled && !b.can_reply && <Badge tone="amber">{T.businessNoReply}</Badge>}
            {b.enabled && (
              <Button size="sm" variant="ghost" className="ms-auto" loading={stop.isPending} onClick={() => stop.mutate()}>
                <span className="text-red-700">{T.businessStop}</span>
              </Button>
            )}
          </div>
        )}
        {!(b.connected && b.enabled) && (
          <ol className="list-decimal space-y-1 ps-5 text-sm leading-7 text-slate-600">
            {T.businessSteps.map((step) => (
              <li key={step}>{step}</li>
            ))}
            {status.business_bot_username && <li>{T.businessStepBot(status.business_bot_username)}</li>}
          </ol>
        )}
      </div>
    </Card>
  );
}
