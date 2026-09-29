import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { BellRing, BookOpen, Check, CircleCheck, Clock, ExternalLink, FileText, Lock, PackageSearch, SlidersHorizontal } from "lucide-react";
import { useI18n } from "../../i18n";
import { LogoMark } from "../Logo";
import { Badge, Toggle, buttonClass, cx } from "../ui";
import { useReducedMotion } from "./motion";

// Illustrations of real panel screens, filled with example content. Items inside `.stagger`
// lists enter one after another when the surrounding <Reveal> scrolls into view.

const idx = (i: number) => ({ "--i": i }) as CSSProperties;

function DemoCard({ icon, title, aside, footer, children, className }: { icon: ReactNode; title: string; aside?: ReactNode; footer?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <div className={cx("overflow-hidden rounded-2xl bg-surface text-ink-950 shadow-lift ring-1 ring-line", className)}>
      <div className="flex items-center gap-2.5 border-b border-slate-100 px-5 py-3.5">
        <span className="flex size-8 items-center justify-center rounded-lg bg-brand-50 text-brand-700 [&>svg]:size-4" aria-hidden>
          {icon}
        </span>
        <span className="flex-1 text-sm font-bold">{title}</span>
        {aside}
      </div>
      <div className="p-5">{children}</div>
      {footer && <div className="border-t border-slate-100 bg-slate-50/70 px-5 py-3 text-xs text-slate-500">{footer}</div>}
    </div>
  );
}

export function KnowledgeDemo() {
  const { t } = useI18n();
  const d = t.landing.demos.knowledge;
  return (
    <DemoCard
      icon={<BookOpen />}
      title={d.title}
      aside={
        <span className="flex items-center gap-2 text-[11px] text-slate-500">
          {d.usage}
          <span className="block h-1.5 w-16 overflow-hidden rounded-full bg-slate-100">
            <span className="block h-full w-[24%] rounded-full bg-brand-500" />
          </span>
          <span className="num font-semibold text-ink-800">{d.usageValue}</span>
        </span>
      }
    >
      <ul className="stagger -my-3 divide-y divide-slate-100">
        {d.sections.map((s, i) => (
          <li key={s.label} style={idx(i)} className="flex gap-3 py-3">
            <CircleCheck className="mt-0.5 size-5 shrink-0 text-emerald-500" aria-hidden />
            <div className="min-w-0">
              <div className="text-sm font-bold">{s.label}</div>
              <p className="text-sm leading-6 text-slate-600">{s.text}</p>
            </div>
          </li>
        ))}
        <li style={idx(d.sections.length)} className="py-3">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl border border-dashed border-brand-200 bg-brand-50/50 px-3 py-2.5">
            <FileText className="size-5 shrink-0 text-brand-700" aria-hidden />
            <span className="min-w-0 flex-1 truncate text-sm font-medium">{d.file}</span>
            <Badge tone="green">
              <Check className="size-3" aria-hidden />
              {d.fileStatus}
            </Badge>
          </div>
        </li>
      </ul>
    </DemoCard>
  );
}

export function ProductsDemo() {
  const { t } = useI18n();
  const d = t.landing.demos.products;
  return (
    <DemoCard
      icon={<PackageSearch />}
      title={d.title}
      footer={
        <span className="flex items-center gap-2">
          <span className="size-1.5 rounded-full bg-emerald-500" aria-hidden />
          {d.source}
        </span>
      }
    >
      <div className="flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
        {d.query}:
        {d.chips.map((chip) => (
          <span key={chip} className="rounded-md bg-slate-100 px-2 py-0.5 font-semibold text-ink-800">
            {chip}
          </span>
        ))}
      </div>
      <div className="mt-4 flex items-center justify-between gap-3 rounded-xl bg-slate-50 px-3.5 py-3">
        <div className="min-w-0">
          <div className="text-sm font-bold">{d.name}</div>
          <div className="num text-xs text-slate-500">{d.price}</div>
        </div>
        <Badge tone="red">{d.out}</Badge>
      </div>
      <p className="mb-2 mt-4 text-xs font-semibold text-slate-500">{d.others}</p>
      <ul className="stagger space-y-2">
        {d.variants.map((v, i) => (
          <li key={v.label} style={idx(i)} className="flex items-center justify-between gap-3 rounded-xl border border-emerald-200 bg-emerald-50/60 px-3.5 py-2.5 text-sm">
            <span className="font-medium">{v.label}</span>
            <span className="num font-bold text-emerald-700">{v.stock}</span>
          </li>
        ))}
      </ul>
    </DemoCard>
  );
}

export function HandoffDemo() {
  const { t, f } = useI18n();
  const d = t.landing.demos.handoff;
  const c = t.landing.chat;
  return (
    <div className="overflow-hidden rounded-2xl bg-surface text-ink-950 shadow-lift ring-1 ring-line">
      {/* the browser tab shows the count too */}
      <div className="flex items-end bg-slate-100 px-3 pt-2" aria-hidden>
        <span className="flex max-w-full items-center gap-2 rounded-t-lg bg-surface px-3 py-1.5 text-xs font-medium text-ink-800">
          <LogoMark px={14} className="rounded-[4px]" />
          <span className="truncate">{d.tabCount}</span>
        </span>
      </div>
      <div className="flex items-center gap-2.5 border-b border-slate-100 px-5 py-3.5">
        <span className="flex size-8 items-center justify-center rounded-lg bg-red-50 text-red-700" aria-hidden>
          <BellRing className="size-4" />
        </span>
        <span className="flex-1 text-sm font-bold">{d.title}</span>
        <span className="num inline-flex min-w-5 items-center justify-center rounded-full bg-red-600 px-1.5 text-xs font-semibold leading-5 text-white">
          {f.num(1)}
        </span>
      </div>
      <div className="stagger space-y-4 p-5">
        <div style={idx(0)} className="flex flex-wrap items-center gap-3">
          <span aria-hidden className="flex size-10 items-center justify-center rounded-full bg-brand-100 font-bold text-brand-700">
            N
          </span>
          <span className="ltr flex-1 text-sm font-bold">{c.customer}</span>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-800 ring-1 ring-amber-200">
            <Clock className="size-3.5" aria-hidden />
            {d.waiting}
          </span>
        </div>
        <div style={idx(1)}>
          <div className="mb-1 text-xs font-semibold text-slate-500">{d.question}</div>
          <p className="rounded-xl bg-slate-50 px-3.5 py-2.5 text-sm leading-6">{d.questionText}</p>
        </div>
        <div style={idx(2)}>
          <div className="mb-1 text-xs font-semibold text-slate-500">{d.reason}</div>
          <p className="text-sm leading-6 text-slate-600">{d.reasonText}</p>
        </div>
        {/* illustration only, so these are not real buttons */}
        <div style={idx(3)} className="flex flex-wrap gap-2" aria-hidden>
          <span className={buttonClass("primary", "sm", "pointer-events-none")}>
            <ExternalLink className="size-3.5" />
            {d.reply}
          </span>
          <span className={buttonClass("secondary", "sm", "pointer-events-none")}>{d.resolve}</span>
        </div>
      </div>
    </div>
  );
}

type Tone = "friendly" | "formal";

/** The one live demo: switch tone and emoji and watch the sample reply change. */
export function ToneDemo() {
  const { t } = useI18n();
  const d = t.landing.demos.tone;
  const reduced = useReducedMotion();
  const [tone, setTone] = useState<Tone>("friendly");
  const [emoji, setEmoji] = useState(true);
  const [typing, setTyping] = useState(false);
  const timer = useRef(0);

  useEffect(() => () => clearTimeout(timer.current), []);

  function change(next: { tone?: Tone; emoji?: boolean }) {
    if (next.tone) setTone(next.tone);
    if (next.emoji !== undefined) setEmoji(next.emoji);
    if (reduced) return;
    setTyping(true);
    clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setTyping(false), 550);
  }

  const reply = d.replies[emoji ? (`${tone}Emoji` as const) : tone];
  const options: { value: Tone; label: string }[] = [
    { value: "friendly", label: d.friendly },
    { value: "formal", label: d.formal },
  ];

  return (
    <DemoCard
      icon={<SlidersHorizontal />}
      title={d.title}
      aside={<span className="rounded-full bg-accent-300 px-2.5 py-0.5 text-[11px] font-bold text-night-900">{d.tryIt}</span>}
    >
      <div className="flex flex-wrap items-center justify-between gap-4">
        <fieldset>
          <legend className="sr-only">{d.title}</legend>
          <div className="relative grid grid-cols-2 rounded-xl bg-slate-100 p-1">
            <span
              aria-hidden
              className={cx(
                "absolute inset-y-1 start-1 w-[calc(50%-0.25rem)] rounded-lg bg-surface shadow-sm transition-transform duration-300 ease-[var(--ease-out-soft)]",
                tone === "formal" && "translate-x-full rtl:-translate-x-full",
              )}
            />
            {options.map((o) => (
              <label
                key={o.value}
                className={cx(
                  "relative z-10 flex min-h-9 cursor-pointer items-center justify-center rounded-lg px-5 text-sm font-semibold transition-colors",
                  "has-focus-visible:outline-2 has-focus-visible:outline-brand-500",
                  tone === o.value ? "text-ink-950" : "text-slate-500 hover:text-ink-900",
                )}
              >
                <input type="radio" name="tone-demo" value={o.value} checked={tone === o.value} onChange={() => change({ tone: o.value })} className="sr-only" />
                {o.label}
              </label>
            ))}
          </div>
        </fieldset>
        <span className="flex items-center gap-2.5 text-sm font-medium text-slate-600">
          {d.emoji}
          <Toggle checked={emoji} onChange={(v) => change({ emoji: v })} label={d.emoji} />
        </span>
      </div>

      <div className="mt-5 flex min-h-40 flex-col gap-2.5 rounded-xl bg-slate-50 p-4">
        <p className="max-w-[85%] self-start rounded-2xl rounded-ss-md bg-surface px-3.5 py-2 text-[13.5px] leading-6 shadow-sm ring-1 ring-slate-200/70">{d.question}</p>
        <div aria-live="polite" className="flex flex-col items-end">
          {typing ? (
            <span className="animate-fade-in flex items-center gap-1 rounded-2xl rounded-se-md bg-brand-100 px-3.5 py-3" aria-label={t.landing.chat.typing}>
              <span className="typing-dot size-1.5 rounded-full bg-brand-500" />
              <span className="typing-dot size-1.5 rounded-full bg-brand-500 [animation-delay:0.2s]" />
              <span className="typing-dot size-1.5 rounded-full bg-brand-500 [animation-delay:0.4s]" />
            </span>
          ) : (
            <p key={reply} className="animate-msg-in max-w-[85%] rounded-2xl rounded-se-md bg-brand-600 px-3.5 py-2 text-[13.5px] leading-6 text-white">
              {reply}
            </p>
          )}
        </div>
      </div>

      <div className="mt-4">
        <div className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-slate-500">
          <Lock className="size-3.5" aria-hidden />
          {d.rules}
        </div>
        <p className="rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm text-slate-700">{d.rulesText}</p>
      </div>
    </DemoCard>
  );
}
