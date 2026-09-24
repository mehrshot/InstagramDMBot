import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera, CheckCircle2 } from "lucide-react";
import { api } from "../api/client";
import { keys } from "../api/queries";
import type { InstagramStatus } from "../api/types";
import { useToast } from "../components/toast";
import { Alert, Badge, Button, Card, CardHeader, ConfirmDialog, PageHeader, PageLoading } from "../components/ui";
import { useI18n } from "../i18n";
import { errorMessage } from "../lib/errors";

/** Fetches a fresh connect link on every click (links expire after 15 minutes) and leaves for Instagram. */
export function useConnectInstagram() {
  const { t } = useI18n();
  const toast = useToast();
  return useMutation({
    mutationFn: () => api<{ url: string }>("/instagram/connect-url"),
    onSuccess: ({ url }) => {
      window.location.href = url;
    },
    onError: (err) => toast.error(errorMessage(err, t)),
  });
}

export default function Instagram() {
  const { t, f } = useI18n();
  const toast = useToast();
  const qc = useQueryClient();
  const [confirm, setConfirm] = useState(false);
  const { data, isPending, error } = useQuery({ queryKey: keys.instagram, queryFn: () => api<InstagramStatus>("/instagram") });
  const connect = useConnectInstagram();

  const disconnect = useMutation({
    mutationFn: () => api("/instagram", { method: "DELETE" }),
    onSuccess: () => {
      setConfirm(false);
      toast.success(t.instagram.disconnected);
      qc.invalidateQueries({ queryKey: keys.instagram });
      qc.invalidateQueries({ queryKey: keys.dashboard });
    },
    onError: (err) => toast.error(errorMessage(err, t)),
  });

  if (isPending) return <PageLoading />;
  if (error) return <Alert kind="error">{errorMessage(error, t)}</Alert>;

  const connectButton = (label: string) => (
    <Button onClick={() => connect.mutate()} loading={connect.isPending || connect.isSuccess} icon={<Camera className="size-4" />}>
      {connect.isSuccess ? t.instagram.redirecting : label}
    </Button>
  );

  return (
    <div className="max-w-2xl space-y-6">
      <PageHeader title={t.instagram.title} />

      <Card>
        <CardHeader
          title={t.nav.instagram}
          action={
            !data.connected ? (
              <Badge>{t.instagram.notConnected}</Badge>
            ) : data.active ? (
              <Badge tone="green">{t.instagram.connected}</Badge>
            ) : (
              <Badge tone="amber">{t.instagram.inactive}</Badge>
            )
          }
        />
        <div className="space-y-4 p-5">
          {data.connected && (
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-slate-500">{t.instagram.connectedAs}</dt>
                <dd className="ltr mt-0.5 font-semibold text-slate-900">
                  {data.username ? (
                    <a href={`https://instagram.com/${data.username}`} target="_blank" rel="noopener noreferrer" className="hover:underline">
                      @{data.username}
                    </a>
                  ) : (
                    data.ig_user_id
                  )}
                </dd>
              </div>
              {data.token_expires_at && (
                <div>
                  <dt className="text-slate-500">{t.instagram.tokenExpires}</dt>
                  <dd className="mt-0.5 font-medium text-slate-900">{f.date(data.token_expires_at)}</dd>
                </div>
              )}
            </dl>
          )}

          {data.connected && !data.active && <Alert kind="warning">{t.instagram.inactiveHint}</Alert>}

          {(!data.connected || !data.active) && (
            <div className="rounded-lg bg-slate-50 p-4 text-sm leading-7">
              <div className="mb-2 font-semibold text-slate-800">{t.instagram.beforeTitle}</div>
              <ul className="space-y-2">
                <li className="flex gap-2">
                  <CheckCircle2 className="mt-1 size-4 shrink-0 text-brand-500" />
                  <span>{t.instagram.beforeProfessional}</span>
                </li>
                <li className="flex gap-2">
                  <CheckCircle2 className="mt-1 size-4 shrink-0 text-brand-500" />
                  <span>
                    {t.instagram.beforeMessages}
                    <br />
                    <code className="mt-1 inline-block rounded bg-white px-2 py-0.5 text-xs text-slate-700 ring-1 ring-slate-200" dir="ltr">
                      Settings → Messages and calls → Connected tools → Allow access to messages
                    </code>
                  </span>
                </li>
              </ul>
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            {!data.connected && connectButton(t.instagram.connect)}
            {data.connected && !data.active && connectButton(t.instagram.reconnect)}
            {data.connected && (
              <Button variant="secondary" onClick={() => setConfirm(true)}>
                {t.instagram.disconnect}
              </Button>
            )}
          </div>
        </div>
      </Card>

      <ConfirmDialog
        open={confirm}
        onClose={() => setConfirm(false)}
        onConfirm={() => disconnect.mutate()}
        loading={disconnect.isPending}
        danger
        title={t.instagram.disconnectConfirmTitle}
        body={t.instagram.disconnectConfirmBody}
        confirmLabel={t.instagram.disconnect}
        cancelLabel={t.common.cancel}
      />
    </div>
  );
}
