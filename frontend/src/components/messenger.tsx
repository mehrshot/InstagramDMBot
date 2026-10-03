import { useState, type ReactNode } from "react";
import { useMutation } from "@tanstack/react-query";
import { Bot, ExternalLink, Link2, Lock, Send, Smartphone, Trash2 } from "lucide-react";
import { api } from "../api/client";
import type { BaleStatus, TelegramLink } from "../api/types";
import { useI18n } from "../i18n";
import { errorMessage } from "../lib/errors";
import { CopyButton } from "./channel";
import { useToast } from "./toast";
import { Alert, Badge, Button, Card, CardHeader, ConfirmDialog, ExternalButton, Field, Input, LinkButton, Toggle } from "./ui";

/**
 * The parts Telegram and Bale have in common. Each messenger is its own channel with its own
 * page and API (/telegram, /bale); these components take which one.
 */
export type Platform = "telegram" | "bale";
type Status = BaleStatus; // TelegramStatus has all of these too

function useCopy(platform: Platform) {
  const { t } = useI18n();
  return { S: platform === "bale" ? t.launch.bale : t.launch.telegram, G: t.launch.telegram };
}

export function EnabledCard({ platform, status, onChange }: { platform: Platform; status: Status; onChange: (s: Status) => void }) {
  const { t } = useI18n();
  const { S } = useCopy(platform);
  const toast = useToast();
  const toggle = useMutation({
    mutationFn: (enabled: boolean) => api<Status>(`/${platform}`, { method: "PATCH", json: { enabled } }),
    onSuccess: onChange,
    onError: (err) => toast.error(errorMessage(err, t)),
  });
  return (
    <Card className="flex flex-wrap items-center justify-between gap-4 p-5 sm:p-6">
      <div className="min-w-0">
        <div className="font-bold text-ink-950">{S.enabled}</div>
        <div className="mt-0.5 text-sm text-slate-500">{S.enabledHint}</div>
      </div>
      <Toggle checked={status.enabled} onChange={(v) => toggle.mutate(v)} disabled={toggle.isPending} label={S.enabled} />
    </Card>
  );
}

export function ShopLink({ platform, status }: { platform: Platform; status: Status }) {
  const { S, G } = useCopy(platform);
  if (!status.shop_link) return null;
  return (
    <Card className="overflow-hidden">
      <CardHeader icon={<Link2 />} title={S.shopLinkTitle} subtitle={S.shopLinkHint} />
      <div className="space-y-3 p-5 sm:px-6">
        <div className="flex flex-wrap items-center gap-2">
          <code dir="ltr" className="min-w-0 flex-1 truncate rounded-xl bg-fill px-3.5 py-2.5 text-sm font-semibold text-ink-900">
            {status.shop_link}
          </code>
          <CopyButton value={status.shop_link} size="md" />
          <ExternalButton href={status.shop_link} variant="soft" icon={<ExternalLink className="size-4" />}>
            {G.open}
          </ExternalButton>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
          <span className="font-semibold text-ink-900">{G.shopCode}:</span>
          <code dir="ltr" className="rounded-lg bg-fill px-2 py-1 font-bold text-ink-900">
            {status.shop_code}
          </code>
          <span className="text-xs text-slate-500">{G.shopCodeHint}</span>
        </div>
      </div>
    </Card>
  );
}

export function OwnerLink({ platform, status, onChange }: { platform: Platform; status: Status; onChange: () => void }) {
  const { t, f } = useI18n();
  const { S, G } = useCopy(platform);
  const toast = useToast();
  const [removing, setRemoving] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => api<TelegramLink>(`/${platform}/link`, { method: "POST" }),
    onError: (err) => toast.error(errorMessage(err, t)),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api(`/${platform}/admins/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      setRemoving(null);
      onChange();
    },
    onError: (err) => toast.error(errorMessage(err, t)),
  });

  return (
    <Card>
      <CardHeader icon={<Smartphone />} title={S.linkTitle} subtitle={S.linkHint} />
      <div className="space-y-4 p-5 sm:px-6">
        {status.admins.length > 0 && (
          <div>
            <div className="mb-2 text-xs font-semibold text-slate-500">{G.linkedAccounts}</div>
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
                  {!a.notify && <Badge tone="amber">{G.notifyOff}</Badge>}
                  <Button size="sm" variant="ghost" icon={<Trash2 className="size-4" />} onClick={() => setRemoving(a.id)}>
                    {G.remove}
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {create.data && (
          <Alert kind="info">
            <p>{G.linkReady}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <a href={create.data.url} target="_blank" rel="noopener noreferrer" dir="ltr" className="break-all font-bold text-brand-700 underline">
                {create.data.url}
              </a>
              <CopyButton value={create.data.url} />
            </div>
            <p className="mt-2 text-xs opacity-80">{G.linkExpires(f.time(create.data.expires_at))}</p>
          </Alert>
        )}

        <Button icon={<Send className="size-4" />} loading={create.isPending} onClick={() => create.mutate()} variant={status.admins.length ? "secondary" : "primary"}>
          {S.linkButton}
        </Button>
      </div>
      <ConfirmDialog
        open={removing !== null}
        onClose={() => setRemoving(null)}
        onConfirm={() => removing && remove.mutate(removing)}
        loading={remove.isPending}
        danger
        title={G.remove}
        body={G.removeConfirm}
        confirmLabel={G.remove}
        cancelLabel={t.common.cancel}
      />
    </Card>
  );
}

export function Locked({ plan, children }: { plan: string; children?: ReactNode }) {
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

export function CustomBot({ platform, status, onChange }: { platform: Platform; status: Status; onChange: (s?: Status) => void }) {
  const { t } = useI18n();
  const { S, G } = useCopy(platform);
  const toast = useToast();
  const [token, setToken] = useState("");
  const [confirm, setConfirm] = useState(false);

  const connect = useMutation({
    mutationFn: () => api<Status>(`/${platform}/custom-bot`, { method: "PUT", json: { token: token.trim() } }),
    onSuccess: (data) => {
      setToken("");
      onChange(data);
    },
    onError: (err) => toast.error(errorMessage(err, t)),
  });
  const disconnect = useMutation({
    mutationFn: () => api(`/${platform}/custom-bot`, { method: "DELETE" }),
    onSuccess: () => {
      setConfirm(false);
      onChange();
    },
    onError: (err) => toast.error(errorMessage(err, t)),
  });

  const bot = status.custom_bot;
  return (
    <Card>
      <CardHeader icon={<Bot />} title={S.customTitle} subtitle={S.customHint} />
      <div className="space-y-4 p-5 sm:px-6">
        {!status.custom_bot_allowed && !bot?.active ? (
          <Locked plan={G.planPro} />
        ) : bot?.active ? (
          <div className="flex flex-wrap items-center gap-3">
            <Badge tone="green">{G.customConnected(bot.username)}</Badge>
            <ExternalButton href={bot.link} size="sm" variant="soft" icon={<ExternalLink className="size-4" />}>
              {G.open}
            </ExternalButton>
            <Button size="sm" variant="ghost" className="ms-auto" onClick={() => setConfirm(true)}>
              <span className="text-red-700">{G.disconnect}</span>
            </Button>
          </div>
        ) : (
          <>
            {bot?.last_error && <Alert kind="warning">{bot.last_error}</Alert>}
            <ol className="list-decimal space-y-1 ps-5 text-sm leading-7 text-slate-600">
              {S.customSteps.map((step) => (
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
              <Field label={G.tokenLabel} className="min-w-64 flex-1">
                {(id) => <Input id={id} dir="ltr" value={token} onChange={(e) => setToken(e.target.value)} placeholder="123456789:AA…" autoComplete="off" />}
              </Field>
              <Button type="submit" loading={connect.isPending} disabled={token.trim().length < 10}>
                {G.connect}
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
        title={G.disconnect}
        body={G.customDisconnectConfirm}
        confirmLabel={G.disconnect}
        cancelLabel={t.common.cancel}
      />
    </Card>
  );
}
