import { useEffect, useState } from "react";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Bell, BellOff, CheckCheck, Clock, ExternalLink, MessageSquare, PartyPopper } from "lucide-react";
import { api } from "../api/client";
import { keys } from "../api/queries";
import type { HandoffItem, HandoffPage } from "../api/types";
import { Avatar, MessageText, useCustomerName } from "../components/conversation";
import FaqDialog from "../components/FaqDialog";
import { useToast } from "../components/toast";
import { Alert, Badge, Button, Card, EmptyState, ExternalButton, LinkButton, PageHeader, PageLoading, Tabs, cx } from "../components/ui";
import { useI18n } from "../i18n";
import { errorMessage } from "../lib/errors";
import { useNotificationPermission } from "../lib/notifications";

type Status = "open" | "resolved";
const PAGE = 30;
const HOUR = 3600_000;

export default function Handoffs() {
  const { t, f } = useI18n();
  const [status, setStatus] = useState<Status>("open");
  const [faq, setFaq] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());

  // keep "waiting for 14 minutes" fresh
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(id);
  }, []);

  const list = useInfiniteQuery({
    queryKey: [...keys.handoffs, status],
    queryFn: ({ pageParam }) => api<HandoffPage>("/handoffs", { query: { status, offset: pageParam, limit: PAGE } }),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => {
      const loaded = pages.reduce((n, p) => n + p.items.length, 0);
      return loaded < last.total ? loaded : undefined;
    },
    refetchInterval: 20_000,
  });
  const items = list.data?.pages.flatMap((p) => p.items) ?? [];
  const total = list.data?.pages[0]?.total;

  return (
    <div className="space-y-6">
      <PageHeader title={t.handoffs.title} subtitle={t.handoffs.subtitle} action={<NotificationButton />} />

      <Tabs
        value={status}
        onChange={setStatus}
        items={[
          { value: "open", label: t.handoffs.tabOpen, count: status === "open" && total ? f.num(total) : undefined },
          { value: "resolved", label: t.handoffs.tabResolved },
        ]}
      />

      {status === "open" && items.length > 0 && <p className="text-sm text-slate-500">{t.handoffs.autoCloseNote}</p>}

      {list.isPending ? (
        <PageLoading />
      ) : list.error ? (
        <Alert kind="error">{errorMessage(list.error, t)}</Alert>
      ) : items.length === 0 ? (
        <Card>
          {status === "open" ? (
            <EmptyState icon={<PartyPopper className="size-12" />} title={t.handoffs.emptyOpen} />
          ) : (
            <EmptyState icon={<CheckCheck className="size-12" />} title={t.handoffs.emptyResolved} />
          )}
        </Card>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <HandoffCard key={item.conversation_id} item={item} now={now} onAddFaq={() => setFaq(item.handoff.question)} />
          ))}
          {list.hasNextPage && (
            <div className="text-center">
              <Button variant="ghost" size="sm" loading={list.isFetchingNextPage} onClick={() => list.fetchNextPage()}>
                {t.common.loadMore}
              </Button>
            </div>
          )}
        </div>
      )}

      <FaqDialog question={faq} onClose={() => setFaq(null)} />
    </div>
  );
}

function HandoffCard({ item, now, onAddFaq }: { item: HandoffItem; now: number; onAddFaq: () => void }) {
  const { t, f } = useI18n();
  const toast = useToast();
  const qc = useQueryClient();
  const name = useCustomerName()(item.customer_username, item.customer_igsid);
  const h = item.handoff;
  const open = h.status === "open";
  const late = open && now - new Date(h.handed_off_at).getTime() > HOUR;

  const resolve = useMutation({
    mutationFn: () => api(`/handoffs/${item.conversation_id}/resolve`, { method: "POST" }),
    onSuccess: () => {
      toast.success(t.handoffs.resolved);
      qc.invalidateQueries({ queryKey: keys.handoffs });
      qc.invalidateQueries({ queryKey: keys.dashboard });
      qc.invalidateQueries({ queryKey: keys.conversations });
    },
    onError: (err) => toast.error(errorMessage(err, t)),
  });

  return (
    <Card className={cx("p-4 sm:p-5", late && "border-amber-300")}>
      <div className="flex flex-wrap items-start gap-3">
        <Avatar name={name} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {item.customer_username ? (
              <a href={`https://instagram.com/${item.customer_username}`} target="_blank" rel="noopener noreferrer" dir="auto" className="font-semibold text-slate-900 hover:underline">
                {name}
              </a>
            ) : (
              <span dir="auto" className="font-semibold text-slate-900">{name}</span>
            )}
            {open ? (
              <Badge tone={late ? "amber" : "red"}>
                <Clock className="size-3" />
                {t.handoffs.waitingFor(f.duration(h.handed_off_at, now))}
              </Badge>
            ) : (
              <Badge tone="green">{h.resolved_by === "owner_reply" ? t.handoffs.resolvedByOwner : t.handoffs.resolvedManual}</Badge>
            )}
            {!open && h.resolved_at && <span className="text-xs text-slate-400">{f.smart(h.resolved_at)}</span>}
          </div>

          <div className="mt-3 rounded-lg bg-slate-50 px-4 py-3">
            <div className="mb-1 text-xs font-medium text-slate-500">{t.handoffs.question}</div>
            <div className="user-text text-sm leading-7 text-slate-800">
              <MessageText text={h.question} />
            </div>
          </div>
          {h.reason && (
            <p className="mt-2 text-xs text-slate-500">
              {t.handoffs.reason}: {h.reason}
            </p>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            {open && item.instagram_url && (
              <ExternalButton href={item.instagram_url} size="sm" icon={<ExternalLink className="size-4" />}>
                {t.common.replyInInstagram}
              </ExternalButton>
            )}
            <LinkButton to={`/inbox/${item.conversation_id}`} size="sm" variant="secondary" icon={<MessageSquare className="size-4" />}>
              {t.common.viewConversation}
            </LinkButton>
            {open && (
              <Button size="sm" variant="secondary" loading={resolve.isPending} onClick={() => resolve.mutate()} title={t.handoffs.resolveHint}>
                {t.handoffs.resolve}
              </Button>
            )}
            <Button size="sm" variant="ghost" onClick={onAddFaq}>
              {t.common.addToKnowledge}
            </Button>
          </div>
        </div>
      </div>
    </Card>
  );
}

function NotificationButton() {
  const { t } = useI18n();
  const { permission, request } = useNotificationPermission();
  if (permission === "unsupported") return null;
  if (permission === "granted")
    return (
      <span className="inline-flex items-center gap-1.5 text-sm text-emerald-700">
        <Bell className="size-4" />
        {t.handoffs.notificationsOn}
      </span>
    );
  if (permission === "denied")
    return (
      <span className="inline-flex items-center gap-1.5 text-sm text-slate-500">
        <BellOff className="size-4" />
        {t.handoffs.notificationsBlocked}
      </span>
    );
  return (
    <Button variant="soft" size="sm" icon={<Bell className="size-4" />} onClick={request}>
      {t.handoffs.enableNotifications}
    </Button>
  );
}
