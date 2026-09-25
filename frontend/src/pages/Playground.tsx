import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router";
import { useMutation } from "@tanstack/react-query";
import { Bot, ChevronDown, PackageSearch, RotateCcw, Send } from "lucide-react";
import { api } from "../api/client";
import { useMe } from "../api/queries";
import type { PlaygroundReply, PlaygroundTurn } from "../api/types";
import { Alert, Badge, Button, Card, PageHeader, Textarea, cx } from "../components/ui";
import { useI18n } from "../i18n";
import { PostCard } from "../components/PostCard";
import { errorMessage } from "../lib/errors";
import { playgroundKey, setFlag } from "../lib/storage";

const MAX_TURNS = 30; // API limit for the whole history

type Turn = PlaygroundTurn & { reply?: PlaygroundReply };

export default function Playground() {
  const { t } = useI18n();
  const { data: me } = useMe();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState("");
  const [aiReady, setAiReady] = useState(true);
  const bottom = useRef<HTMLDivElement>(null);

  const chat = useMutation({
    // the panel keeps the history and sends all of it each time; nothing is stored server-side
    mutationFn: (history: Turn[]) =>
      api<PlaygroundReply>("/playground/chat", { method: "POST", json: { messages: history.map(({ role, text }) => ({ role, text })) } }),
    onSuccess: (reply) => {
      setAiReady(reply.ai_ready);
      setTurns((list) => [...list, { role: "bot", text: reply.reply, reply }]);
      if (me) setFlag(playgroundKey(me.shop.id));
    },
  });

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, chat.isPending]);

  const full = turns.length >= MAX_TURNS - 1;

  function send(message: string) {
    const clean = message.trim();
    if (!clean || chat.isPending || full) return;
    const history: Turn[] = [...turns, { role: "customer", text: clean.slice(0, 2000) }];
    setTurns(history);
    setText("");
    chat.mutate(history);
  }

  function retry() {
    if (turns.at(-1)?.role === "customer") chat.mutate(turns);
  }

  function restart() {
    chat.reset();
    setTurns([]);
    setText("");
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    send(text);
  }

  return (
    <div className="flex h-[calc(100dvh-7rem)] min-h-[32rem] flex-col lg:h-[calc(100dvh-4rem)]">
      <PageHeader
        title={t.playground.title}
        subtitle={t.playground.subtitle}
        action={
          turns.length > 0 && (
            <Button variant="secondary" size="sm" icon={<RotateCcw className="size-4" />} onClick={restart}>
              {t.playground.restart}
            </Button>
          )
        }
      />

      {!aiReady && <Alert kind="info" className="mb-4">{t.playground.aiNotReady}</Alert>}

      <Card className="flex min-h-0 flex-1 flex-col">
        <div className="flex-1 space-y-4 overflow-y-auto p-4 sm:p-5">
          {turns.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
              <Bot className="size-12 text-slate-300" />
              <p className="text-slate-500">{t.playground.empty}</p>
              <div className="flex flex-wrap justify-center gap-2">
                {t.playground.suggestions.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => send(s)}
                    className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 hover:border-brand-300 hover:text-brand-700"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {turns.map((turn, i) => (turn.role === "customer" ? <CustomerBubble key={i} text={turn.text} /> : <BotBubble key={i} turn={turn} />))}

          {chat.isPending && (
            <div className="flex justify-end">
              <div className="flex items-center gap-2 rounded-2xl bg-brand-50 px-4 py-3 text-sm text-brand-700">
                <span className="flex gap-1">
                  <span className="typing-dot size-1.5 rounded-full bg-brand-500" />
                  <span className="typing-dot size-1.5 rounded-full bg-brand-500 [animation-delay:0.2s]" />
                  <span className="typing-dot size-1.5 rounded-full bg-brand-500 [animation-delay:0.4s]" />
                </span>
                {t.playground.typing}
              </div>
            </div>
          )}

          {chat.error && (
            <Alert kind="error" action={<Button size="sm" variant="secondary" onClick={retry}>{t.common.retry}</Button>}>
              {errorMessage(chat.error, t)}
            </Alert>
          )}
          {full && <Alert kind="warning">{t.playground.limit}</Alert>}
          <div ref={bottom} />
        </div>

        <form onSubmit={onSubmit} className="flex items-end gap-2 border-t border-slate-100 p-3">
          <Textarea
            rows={1}
            className="max-h-32 min-h-10 resize-none"
            placeholder={t.playground.placeholder}
            value={text}
            maxLength={2000}
            disabled={full}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                send(text);
              }
            }}
          />
          <Button type="submit" disabled={!text.trim() || chat.isPending || full} aria-label={t.playground.send} className="shrink-0">
            <Send className="size-4 rtl:-scale-x-100" />
          </Button>
        </form>
      </Card>
    </div>
  );
}

function CustomerBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-start">
      <div className="user-text max-w-[85%] rounded-2xl rounded-ss-sm bg-slate-100 px-4 py-2.5 text-sm leading-7 text-slate-800 sm:max-w-[70%]">{text}</div>
    </div>
  );
}

function BotBubble({ turn }: { turn: Turn }) {
  const { t } = useI18n();
  const r = turn.reply;
  return (
    <div className="flex flex-col items-end gap-1.5">
      <div className="flex max-w-[85%] items-end gap-2 sm:max-w-[70%]">
        <div className="user-text rounded-2xl rounded-se-sm bg-brand-600 px-4 py-2.5 text-sm leading-7 text-white">{turn.text}</div>
        <span className="mb-1 flex size-7 shrink-0 items-center justify-center rounded-full bg-brand-100 text-brand-700">
          <Bot className="size-4" />
        </span>
      </div>

      {r?.unanswered && (
        <div className="me-9 max-w-[85%] rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 sm:max-w-[70%]">
          <div className="font-medium">{t.playground.unansweredLabel}</div>
          {r.handoff_reason && (
            <div className="mt-0.5 opacity-80">
              {t.playground.reason}: {r.handoff_reason}
            </div>
          )}
          <Link to="/knowledge" className="mt-1 inline-block font-semibold text-amber-800 underline">
            {t.playground.unansweredAdd}
          </Link>
        </div>
      )}

      {r?.posts.map((post) => <PostCard key={post.permalink} post={post} className="me-9" />)}

      {r && r.product_lookups.some((l) => l.tool === "search_products") && (
        <Lookups lookups={r.product_lookups.filter((l) => l.tool === "search_products")} />
      )}
    </div>
  );
}

type Lookup = { tool?: string; arguments?: Record<string, unknown>; result?: { matches?: ProductInfo[]; other_in_stock_variants?: ProductInfo[] } };
type ProductInfo = { name?: string; color?: string; size?: string; price_toman?: number; in_stock?: boolean; stock_count?: number; sku?: string };

/** "The bot checked these products" — shows owners why the bot said what it said. */
function Lookups({ lookups }: { lookups: Record<string, unknown>[] }) {
  const { t, f } = useI18n();
  const [open, setOpen] = useState(false);
  const items = lookups as Lookup[];

  return (
    <div className="me-9 w-full max-w-[85%] rounded-lg border border-slate-200 bg-white text-xs sm:max-w-[70%]">
      <button type="button" onClick={() => setOpen(!open)} className="flex w-full items-center gap-2 px-3 py-2 text-slate-600 hover:bg-slate-50">
        <PackageSearch className="size-4 text-slate-400" />
        <span className="flex-1 text-start font-medium">{t.playground.lookups}</span>
        <ChevronDown className={cx("size-4 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="space-y-3 border-t border-slate-100 px-3 py-2">
          {items.map((l, i) => {
            const args = Object.entries(l.arguments ?? {}).filter(([, v]) => v !== null && v !== "");
            const matches = l.result?.matches ?? [];
            const others = l.result?.other_in_stock_variants ?? [];
            return (
              <div key={i}>
                <div className="mb-1 text-slate-500">
                  {t.playground.lookupQuery}: {args.map(([k, v]) => <Badge key={k} className="me-1">{String(v)}</Badge>)}
                </div>
                {matches.length === 0 && <div className="text-slate-400">{t.playground.lookupNoMatch}</div>}
                <ProductList items={matches} f={f} />
                {others.length > 0 && (
                  <>
                    <div className="mt-2 mb-1 text-slate-500">{t.playground.otherVariants}</div>
                    <ProductList items={others} f={f} />
                  </>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ProductList({ items, f }: { items: ProductInfo[]; f: ReturnType<typeof useI18n>["f"] }) {
  const { t } = useI18n();
  if (!items.length) return null;
  return (
    <ul className="divide-y divide-slate-100 rounded-md bg-slate-50">
      {items.map((p, i) => (
        <li key={i} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-2 py-1.5">
          <span className="font-medium text-slate-800">{p.name}</span>
          {p.color && <span className="text-slate-500">{p.color}</span>}
          {p.size && <span className="num text-slate-500">{p.size}</span>}
          {p.price_toman != null && <span className="num text-slate-700">{f.num(p.price_toman)}</span>}
          {p.in_stock === false && <Badge tone="red">{t.products.outOfStock}</Badge>}
          {p.in_stock && p.stock_count != null && <span className="num text-emerald-700">× {f.num(p.stock_count)}</span>}
        </li>
      ))}
    </ul>
  );
}
