import { useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageCircle } from "lucide-react";
import { api } from "../api/client";
import { keys } from "../api/queries";
import type { BaleStatus } from "../api/types";
import { CustomBot, EnabledCard, OwnerLink, ShopLink } from "../components/messenger";
import { Alert, PageHeader, PageLoading } from "../components/ui";
import { useI18n } from "../i18n";
import { errorMessage } from "../lib/errors";

/** Bale (بله): its own channel, separate from Telegram (a shop may use one, both or neither). */
export default function Bale() {
  const { t } = useI18n();
  const B = t.launch.bale;
  const qc = useQueryClient();
  const status = useQuery({ queryKey: keys.bale, queryFn: () => api<BaleStatus>("/bale") });

  const refresh = (data?: unknown) => {
    if (data) qc.setQueryData(keys.bale, data);
    else qc.invalidateQueries({ queryKey: keys.bale });
    qc.invalidateQueries({ queryKey: keys.dashboard });
  };

  const header = <PageHeader icon={<MessageCircle />} title={B.title} subtitle={B.subtitle} />;
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
        <Alert kind="warning">{B.notReady}</Alert>
      </>
    );

  return (
    <div className="max-w-4xl space-y-6">
      {header}
      <EnabledCard platform="bale" status={s} onChange={refresh} />
      <ShopLink platform="bale" status={s} />
      <OwnerLink platform="bale" status={s} onChange={refresh} />
      <CustomBot platform="bale" status={s} onChange={refresh} />
      <p className="text-sm leading-6 text-slate-500">{B.notAvailable}</p>
    </div>
  );
}
