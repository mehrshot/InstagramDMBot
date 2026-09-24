import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, ExternalLink, Inbox as InboxIcon, MessageSquare, Pause, Play, Search } from "lucide-react";
import { api } from "../api/client";
import { keys } from "../api/queries";
import type { Conversation, ConversationDetail, ConversationFilter, ConversationPage } from "../api/types";
import { Avatar, MessageBubble, isIndefinitePause, useCustomerName, useMessagePreview } from "../components/conversation";
import { useToast } from "../components/toast";
import { Alert, Badge, Button, EmptyState, ExternalButton, Input, PageLoading, Spinner, Tabs, cx } from "../components/ui";
import { useI18n } from "../i18n";
import { errorMessage } from "../lib/errors";

const PAGE = 30;
// No WebSocket: poll while the tab is visible (TanStack pauses intervals in background tabs).
const POLL_MS = 12_000;

export default function Inbox() {
  const { id } = useParams();
  return (
    <div className="-mx-4 -my-6 flex h-[calc(100dvh-3.5rem)] sm:-mx-6 lg:-my-8 lg:h-dvh">
      <div className={cx("w-full shrink-0 border-e border-slate-200 bg-white lg:flex lg:w-96 lg:flex-col", id ? "hidden" : "flex flex-col")}>
        <ConversationList selected={id} />
      </div>
      <div className={cx("min-w-0 flex-1", id ? "flex flex-col" : "hidden lg:flex lg:flex-col")}>
        {id ? (
          <ConversationView key={id} id={id} />
        ) : (
          <div className="m-auto">
            <EmptyState icon={<MessageSquare className="size-12" />} title={<SelectPrompt />} />
          </div>
        )}
      </div>
    </div>
  );
}

function SelectPrompt() {
  const { t } = useI18n();
  return <>{t.inbox.selectConversation}</>;
}

function ConversationList({ selected }: { selected?: string }) {
  const { t } = useI18n();
  const [filter, setFilter] = useState<ConversationFilter>("all");
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    const id = setTimeout(() => setSearch(q.trim()), 300);
    return () => clearTimeout(id);
  }, [q]);

  const list = useInfiniteQuery({
    queryKey: [...keys.conversations, filter, search],
    queryFn: ({ pageParam }) => api<ConversationPage>("/conversations", { query: { filter, q: search, offset: pageParam, limit: PAGE } }),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => {
      const loaded = pages.reduce((n, p) => n + p.items.length, 0);
      return loaded < last.total ? loaded : undefined;
    },
    refetchInterval: POLL_MS,
  });

  const items = list.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <>
      <div className="space-y-3 border-b border-slate-100 p-4">
        <h1 className="text-lg font-bold text-slate-900">{t.inbox.title}</h1>
        <Tabs
          value={filter}
          onChange={setFilter}
          items={[
            { value: "all", label: t.inbox.filterAll },
            { value: "needs_owner", label: t.inbox.filterNeedsOwner },
            { value: "unanswered", label: t.inbox.filterUnanswered },
            { value: "paused", label: t.inbox.filterPaused },
          ]}
        />
        <div className="relative">
          <Search className="pointer-events-none absolute start-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
          <Input className="ps-9" placeholder={t.inbox.searchPlaceholder} value={q} maxLength={64} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">
        {list.isPending ? (
          <PageLoading />
        ) : list.error ? (
          <div className="p-4">
            <Alert kind="error">{errorMessage(list.error, t)}</Alert>
          </div>
        ) : items.length === 0 ? (
          <EmptyState icon={<InboxIcon className="size-10" />} title={t.inbox.empty} />
        ) : (
          <ul className="divide-y divide-slate-100">
            {items.map((c) => (
              <ConversationRow key={c.id} c={c} active={c.id === selected} />
            ))}
          </ul>
        )}
        {list.hasNextPage && (
          <div className="p-3 text-center">
            <Button size="sm" variant="ghost" loading={list.isFetchingNextPage} onClick={() => list.fetchNextPage()}>
              {t.common.loadMore}
            </Button>
          </div>
        )}
      </div>
    </>
  );
}

function ConversationRow({ c, active }: { c: Conversation; active: boolean }) {
  const { t, f } = useI18n();
  const name = useCustomerName()(c.customer_username, c.customer_igsid);
  const preview = useMessagePreview();
  const waiting = c.handoff?.status === "open";
  const time = c.last_message?.created_at ?? c.last_customer_message_at;

  return (
    <li>
      <Link
        to={`/inbox/${c.id}`}
        className={cx("flex gap-3 px-4 py-3 transition-colors", active ? "bg-brand-50" : "hover:bg-slate-50", waiting && !active && "bg-red-50/40")}
      >
        <Avatar name={name} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span dir="auto" className="truncate font-medium text-slate-900">{name}</span>
            {time && <span className="ms-auto shrink-0 text-xs text-slate-400">{f.smart(time)}</span>}
          </div>
          {c.last_message && (
            <p className="mt-0.5 truncate text-sm text-slate-500">
              {c.last_message.sender === "bot" && <span className="text-slate-400">{t.inbox.senderBot}: </span>}
              {c.last_message.sender === "owner" && <span className="text-slate-400">{t.inbox.senderOwner}: </span>}
              {preview(c.last_message.text)}
            </p>
          )}
          {(waiting || c.bot_paused || c.open_unanswered > 0) && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {waiting && <Badge tone="red">{t.inbox.badgeWaiting}</Badge>}
              {c.bot_paused && <Badge tone="amber">{t.inbox.badgePaused}</Badge>}
              {c.open_unanswered > 0 && !waiting && <Badge tone="neutral">{t.inbox.botDidntKnow}</Badge>}
            </div>
          )}
        </div>
      </Link>
    </li>
  );
}

function ConversationView({ id }: { id: string }) {
  const { t, f } = useI18n();
  const toast = useToast();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const name = useCustomerName();
  const bottom = useRef<HTMLDivElement>(null);
  const [pauseMenu, setPauseMenu] = useState(false);

  const detail = useQuery({
    queryKey: keys.conversation(id),
    queryFn: () => api<ConversationDetail>(`/conversations/${id}`),
    refetchInterval: POLL_MS,
  });

  const messageCount = detail.data?.messages.length ?? 0;
  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [messageCount]);

  const onUpdated = (c: Conversation) => {
    qc.setQueryData<ConversationDetail>(keys.conversation(id), (old) => (old ? { ...old, ...c } : old));
    qc.invalidateQueries({ queryKey: keys.conversations });
  };

  const pause = useMutation({
    mutationFn: (minutes: number | null) => api<Conversation>(`/conversations/${id}/pause`, { method: "POST", json: minutes ? { minutes } : {} }),
    onSuccess: (c) => {
      setPauseMenu(false);
      onUpdated(c);
      toast.success(t.inbox.paused);
    },
    onError: (err) => toast.error(errorMessage(err, t)),
  });

  const resume = useMutation({
    mutationFn: () => api<Conversation>(`/conversations/${id}/resume`, { method: "POST" }),
    onSuccess: (c) => {
      onUpdated(c);
      toast.success(t.inbox.resumed);
    },
    onError: (err) => toast.error(errorMessage(err, t)),
  });

  if (detail.isPending)
    return (
      <div className="flex flex-1 items-center justify-center">
        <Spinner className="size-7" />
      </div>
    );
  if (detail.error)
    return (
      <div className="p-6">
        <Alert kind="error">{errorMessage(detail.error, t)}</Alert>
      </div>
    );

  const c = detail.data;
  const display = name(c.customer_username, c.customer_igsid);
  const waiting = c.handoff?.status === "open";

  return (
    <>
      <header className="flex flex-wrap items-center gap-3 border-b border-slate-200 bg-white px-4 py-3">
        <button type="button" onClick={() => navigate("/inbox")} className="rounded-md p-1 text-slate-500 hover:bg-slate-100 lg:hidden" aria-label={t.inbox.backToList}>
          <ArrowRight className="size-5 ltr:rotate-180" />
        </button>
        <Avatar name={display} className="size-9" />
        <div className="min-w-0 flex-1">
          <div className="truncate font-semibold text-slate-900">
            <span dir="auto">{display}</span>
          </div>
          {c.customer_username && (
            <a href={`https://instagram.com/${c.customer_username}`} target="_blank" rel="noopener noreferrer" className="text-xs text-brand-600 hover:underline">
              {t.inbox.profile}
            </a>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {c.bot_paused ? (
            <Button size="sm" variant="secondary" icon={<Play className="size-4" />} loading={resume.isPending} onClick={() => resume.mutate()}>
              {t.inbox.resume}
            </Button>
          ) : (
            <div className="relative">
              <Button size="sm" variant="secondary" icon={<Pause className="size-4" />} onClick={() => setPauseMenu(!pauseMenu)} loading={pause.isPending}>
                {t.inbox.pause}
              </Button>
              {pauseMenu && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setPauseMenu(false)} />
                  <div className="absolute end-0 z-20 mt-1 w-52 overflow-hidden rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
                    {[
                      [120, t.inbox.pause2h],
                      [1440, t.inbox.pause24h],
                      [null, t.inbox.pauseForever],
                    ].map(([mins, label]) => (
                      <button
                        key={String(mins)}
                        type="button"
                        onClick={() => pause.mutate(mins as number | null)}
                        className="block w-full px-4 py-2 text-start text-sm text-slate-700 hover:bg-slate-50"
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
          {c.instagram_url && (
            <ExternalButton href={c.instagram_url} size="sm" icon={<ExternalLink className="size-4" />}>
              {t.common.replyInInstagram}
            </ExternalButton>
          )}
        </div>
      </header>

      {(waiting || c.bot_paused) && (
        <div className="space-y-2 border-b border-slate-200 bg-slate-50 px-4 py-3">
          {waiting && c.handoff && (
            <Alert kind="error">
              <b>{t.inbox.badgeWaiting}</b>
              {c.handoff.reason && (
                <div className="mt-0.5">
                  {t.inbox.handoffReason}: {c.handoff.reason}
                </div>
              )}
            </Alert>
          )}
          {c.bot_paused && (
            <Alert kind="warning">
              {isIndefinitePause(c.bot_paused_until) ? t.inbox.pausedIndefinitely : t.inbox.pausedUntil(f.smart(c.bot_paused_until!))}
            </Alert>
          )}
        </div>
      )}

      <div className="flex-1 space-y-4 overflow-y-auto bg-slate-50/50 p-4 sm:p-6">
        {c.messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        <div ref={bottom} />
      </div>

      <footer className="border-t border-slate-200 bg-white px-4 py-3 text-center text-xs text-slate-500">{t.inbox.noSendNote}</footer>
    </>
  );
}
