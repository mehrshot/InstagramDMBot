import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, BriefcaseBusiness, ExternalLink, Link2, Lock, Megaphone, Send, Smartphone, Trash2 } from "lucide-react";
import { api } from "../api/client";
import { keys } from "../api/queries";
import type { TelegramLink, TelegramStatus } from "../api/types";
import { CopyButton } from "../components/channel";
import { useToast } from "../components/toast";
import { Alert, Badge, Button, Card, CardHeader, ConfirmDialog, ExternalButton, Field, Input, LinkButton, PageHeader, PageLoading, Toggle } from "../components/ui";
import { useI18n } from "../i18n";
import { errorMessage } from "../lib/errors";

export default function Telegram() {
  const { t } = useI18n();
  const T = t.launch.telegram;
  const toast = useToast();
  const qc = useQueryClient();
  const status = useQuery({ queryKey: keys.telegram, queryFn: () => api<TelegramStatus>("/telegram") });

  const refresh = (data?: TelegramStatus) => {
    if (data) qc.setQueryData(keys.telegram, data);
    else qc.invalidateQueries({ queryKey: keys.telegram });
    qc.invalidateQueries({ queryKey: keys.dashboard });
  };

  const toggle = useMutation({
    mutationFn: (enabled: boolean) => api<TelegramStatus>("/telegram", { method: "PATCH", json: { enabled } }),
    onSuccess: refresh,
    onError: (err) => toast.error(errorMessage(err, t)),
  });

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

      <Card className="flex flex-wrap items-center justify-between gap-4 p-5 sm:p-6">
        <div className="min-w-0">
          <div className="font-bold text-ink-950">{T.enabled}</div>
          <div className="mt-0.5 text-sm text-slate-500">{T.enabledHint}</div>
        </div>
        <Toggle checked={s.enabled} onChange={(v) => toggle.mutate(v)} disabled={toggle.isPending} label={T.enabled} />
      </Card>

      {s.shop_link && <ShopLink link={s.shop_link} />}
      <OwnerLink status={s} onChange={refresh} />
      <Channels status={s} />
      <CustomBot status={s} onChange={refresh} />
      <Business status={s} onChange={refresh} />
    </div>
  );
}

function ShopLink({ link }: { link: string }) {
  const { t } = useI18n();
  const T = t.launch.telegram;
  return (
    <Card className="overflow-hidden">
      <CardHeader icon={<Link2 />} title={T.shopLinkTitle} subtitle={T.shopLinkHint} />
      <div className="flex flex-wrap items-center gap-2 p-5 sm:px-6">
        <code dir="ltr" className="min-w-0 flex-1 truncate rounded-xl bg-fill px-3.5 py-2.5 text-sm font-semibold text-ink-900">
          {link}
        </code>
        <CopyButton value={link} size="md" />
        <ExternalButton href={link} variant="soft" icon={<ExternalLink className="size-4" />}>
          {T.open}
        </ExternalButton>
      </div>
    </Card>
  );
}

function OwnerLink({ status, onChange }: { status: TelegramStatus; onChange: (s?: TelegramStatus) => void }) {
  const { t, f } = useI18n();
  const T = t.launch.telegram;
  const toast = useToast();
  const [removing, setRemoving] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => api<TelegramLink>("/telegram/link", { method: "POST" }),
    onError: (err) => toast.error(errorMessage(err, t)),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api(`/telegram/admins/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      setRemoving(null);
      onChange();
    },
    onError: (err) => toast.error(errorMessage(err, t)),
  });

  return (
    <Card>
      <CardHeader icon={<Smartphone />} title={T.linkTitle} subtitle={T.linkHint} />
      <div className="space-y-4 p-5 sm:px-6">
        {status.admins.length > 0 && (
          <div>
            <div className="mb-2 text-xs font-semibold text-slate-500">{T.linkedAccounts}</div>
            <ul className="space-y-2">
              {status.admins.map((a) => (
                <li key={a.id} className="flex flex-wrap items-center gap-3 rounded-xl bg-fill px-3.5 py-2.5">
                  <span className="min-w-0 flex-1 text-sm font-semibold text-ink-900">
                    {a.first_name || a.username || a.telegram_user_id}
                    {a.username && (
                      <span dir="ltr" className="ms-2 font-normal text-slate-500">
                        @{a.username}
                      </span>
                    )}
                  </span>
                  {!a.notify && <Badge tone="amber">{T.notifyOff}</Badge>}
                  <Button size="sm" variant="ghost" icon={<Trash2 className="size-4" />} onClick={() => setRemoving(a.id)}>
                    {T.remove}
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {create.data ? (
          <Alert kind="info">
            <p>{T.linkReady}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <a href={create.data.url} target="_blank" rel="noopener noreferrer" dir="ltr" className="break-all font-bold text-brand-700 underline">
                {create.data.url}
              </a>
              <CopyButton value={create.data.url} />
            </div>
            <p className="mt-2 text-xs opacity-80">{T.linkExpires(f.time(create.data.expires_at))}</p>
          </Alert>
        ) : null}

        <Button icon={<Send className="size-4" />} loading={create.isPending} onClick={() => create.mutate()} variant={status.admins.length ? "secondary" : "primary"}>
          {T.linkButton}
        </Button>
      </div>
      <ConfirmDialog
        open={removing !== null}
        onClose={() => setRemoving(null)}
        onConfirm={() => removing && remove.mutate(removing)}
        loading={remove.isPending}
        danger
        title={T.remove}
        body={T.removeConfirm}
        confirmLabel={T.remove}
        cancelLabel={t.common.cancel}
      />
    </Card>
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

function Locked({ plan, children }: { plan: string; children?: ReactNode }) {
  const { t } = useI18n();
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900 ring-1 ring-amber-200">
      <Lock className="size-4 shrink-0" aria-hidden />
      <span className="flex-1">{t.launch.telegram.locked(plan)}</span>
      {children}
      <LinkButton to="/billing" size="sm" variant="secondary">
        {t.launch.telegram.upgrade}
      </LinkButton>
    </div>
  );
}

function CustomBot({ status, onChange }: { status: TelegramStatus; onChange: (s?: TelegramStatus) => void }) {
  const { t } = useI18n();
  const T = t.launch.telegram;
  const toast = useToast();
  const [token, setToken] = useState("");
  const [confirm, setConfirm] = useState(false);

  const connect = useMutation({
    mutationFn: () => api<TelegramStatus>("/telegram/custom-bot", { method: "PUT", json: { token: token.trim() } }),
    onSuccess: (data) => {
      setToken("");
      onChange(data);
    },
    onError: (err) => toast.error(errorMessage(err, t)),
  });
  const disconnect = useMutation({
    mutationFn: () => api("/telegram/custom-bot", { method: "DELETE" }),
    onSuccess: () => {
      setConfirm(false);
      onChange();
    },
    onError: (err) => toast.error(errorMessage(err, t)),
  });

  const bot = status.custom_bot;
  return (
    <Card>
      <CardHeader icon={<Bot />} title={T.customTitle} subtitle={T.customHint} />
      <div className="space-y-4 p-5 sm:px-6">
        {!status.custom_bot_allowed && !bot?.active ? (
          <Locked plan={T.planPro} />
        ) : bot?.active ? (
          <div className="flex flex-wrap items-center gap-3">
            <Badge tone="green">{T.customConnected(bot.username)}</Badge>
            <ExternalButton href={bot.link} size="sm" variant="soft" icon={<ExternalLink className="size-4" />}>
              {T.open}
            </ExternalButton>
            <Button size="sm" variant="ghost" className="ms-auto" onClick={() => setConfirm(true)}>
              <span className="text-red-700">{T.disconnect}</span>
            </Button>
          </div>
        ) : (
          <>
            {bot?.last_error && <Alert kind="warning">{bot.last_error}</Alert>}
            <ol className="list-decimal space-y-1 ps-5 text-sm leading-7 text-slate-600">
              {T.customSteps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
            <form
              className="flex flex-wrap items-end gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                connect.mutate();
              }}
            >
              <Field label={T.tokenLabel} className="min-w-64 flex-1">
                {(id) => <Input id={id} dir="ltr" value={token} onChange={(e) => setToken(e.target.value)} placeholder="123456789:AA…" autoComplete="off" />}
              </Field>
              <Button type="submit" loading={connect.isPending} disabled={token.trim().length < 10}>
                {T.connect}
              </Button>
            </form>
          </>
        )}
      </div>
      <ConfirmDialog
        open={confirm}
        onClose={() => setConfirm(false)}
        onConfirm={() => disconnect.mutate()}
        loading={disconnect.isPending}
        danger
        title={T.disconnect}
        body={T.customDisconnectConfirm}
        confirmLabel={T.disconnect}
        cancelLabel={t.common.cancel}
      />
    </Card>
  );
}

function Business({ status, onChange }: { status: TelegramStatus; onChange: (s?: TelegramStatus) => void }) {
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
