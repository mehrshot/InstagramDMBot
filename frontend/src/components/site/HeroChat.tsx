import { useEffect, useRef, useState, type ReactNode } from "react";
import { BellRing, Images, PackageSearch, RotateCcw } from "lucide-react";
import { useI18n } from "../../i18n";
import { LogoMark } from "../Logo";
import { cx } from "../ui";
import { useInView, useReducedMotion } from "./motion";

// Who sends each message and when it lands (ms after start). Bot messages show a typing
// indicator for TYPING ms first.
const SCRIPT = [
  { from: "customer", at: 300 },
  { from: "bot", at: 2000 },
  { from: "customer", at: 3700 },
  { from: "bot", at: 5300 },
  { from: "customer", at: 6900 },
  { from: "bot", at: 8500 },
] as const;
const TYPING = 1100;

/**
 * The hero's example sales conversation, as the business owner sees it in the panel. Every message is
 * rendered from the start (so the card never changes height) and revealed in sequence.
 */
export default function HeroChat() {
  const { t } = useI18n();
  const c = t.landing.chat;
  const reduced = useReducedMotion();
  const ref = useRef<HTMLElement>(null);
  const inView = useInView(ref);
  const [shown, setShown] = useState(0);
  const [typing, setTyping] = useState(false);
  const [run, setRun] = useState(0);
  const done = shown >= SCRIPT.length;

  useEffect(() => {
    if (reduced) {
      setShown(SCRIPT.length);
      setTyping(false);
      return;
    }
    if (!inView) return;
    setShown(0);
    setTyping(false);
    const timers: number[] = [];
    SCRIPT.forEach(({ from, at }, i) => {
      if (from === "bot") timers.push(window.setTimeout(() => setTyping(true), at - TYPING));
      timers.push(
        window.setTimeout(() => {
          setTyping(false);
          setShown(i + 1);
        }, at),
      );
    });
    return () => timers.forEach(clearTimeout);
  }, [inView, reduced, run]);

  const texts = [c.m1, c.m2, c.m3, c.m4, c.m5, c.m6];
  // Extras below a bot message; `on` starts their entrance once the message is visible.
  const extras: Record<number, (on: boolean) => ReactNode> = {
    1: (on) => (
      <>
        <span className={cx("inline-flex items-center gap-1.5 text-[11px] font-medium text-slate-500", on && "animate-pop-in [animation-delay:250ms]")}>
          <PackageSearch className="size-3.5 text-brand-700" aria-hidden />
          {c.lookup}
        </span>
        <span
          className={cx(
            "flex w-56 max-w-[85%] items-center gap-2.5 rounded-xl border border-slate-200 bg-surface p-1.5 shadow-sm",
            on && "animate-pop-in [animation-delay:500ms]",
          )}
        >
          <span aria-hidden className="flex size-11 shrink-0 items-center justify-center rounded-lg bg-brand-100 text-brand-700">
            <Images className="size-5" />
          </span>
          <span className="min-w-0">
            <span className="block text-xs font-bold text-ink-900">{c.postTitle}</span>
            <span className="block truncate text-[11px] text-slate-500">{c.postCaption}</span>
          </span>
        </span>
      </>
    ),
    5: (on) => (
      <span
        className={cx(
          "inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-800 ring-1 ring-amber-200",
          on && "animate-pop-in [animation-delay:300ms]",
        )}
      >
        <BellRing className="size-3.5" aria-hidden />
        {c.handedOff}
      </span>
    ),
  };

  return (
    <figure ref={ref} aria-label={c.label} className="relative mx-auto w-full max-w-[27rem] lg:me-0">
      {/* live status, overlapping the card edge */}
      <div className="absolute -top-4 start-6 z-10 inline-flex items-center gap-2 rounded-full bg-surface px-3 py-1.5 text-xs font-semibold text-ink-900 shadow-soft ring-1 ring-line">
        <span className="relative flex size-2" aria-hidden>
          <span className="absolute inset-0 animate-ping rounded-full bg-emerald-400 opacity-60 [animation-duration:2s]" />
          <span className="relative size-2 rounded-full bg-emerald-500" />
        </span>
        {c.botOn}
      </div>

      <div className="overflow-hidden rounded-[1.75rem] bg-surface text-ink-950 shadow-float ring-1 ring-line">
        <div className="flex items-center gap-3 border-b border-slate-100 px-5 pb-3.5 pt-6">
          <span aria-hidden className="flex size-10 items-center justify-center rounded-full bg-brand-100 font-bold text-brand-700">
            N
          </span>
          <div className="min-w-0 flex-1">
            <div className="ltr truncate text-sm font-bold">{c.customer}</div>
            <div className="truncate text-xs text-slate-500">{c.shop}</div>
          </div>
          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-500">{c.example}</span>
        </div>

        <ol className="space-y-3 px-4 py-5 sm:px-5">
          {SCRIPT.map(({ from }, i) => {
            const visible = i < shown;
            const side = from === "customer" ? "items-start" : "items-end";
            return (
              <li key={i} className={cx("relative flex flex-col", side)}>
                {typing && i === shown && from === "bot" && <TypingBubble label={c.typing} />}
                <div className={cx("flex w-full flex-col gap-1.5", side, visible ? "animate-msg-in" : "invisible")}>
                  <p
                    className={cx(
                      "max-w-[85%] rounded-2xl px-3.5 py-2 text-[13.5px] leading-6",
                      from === "customer" ? "rounded-ss-md bg-slate-100 text-ink-900" : "rounded-se-md bg-brand-600 text-white",
                    )}
                  >
                    {texts[i]}
                  </p>
                  {i === 1 && (
                    <span className="flex items-center gap-1.5 text-[11px] text-slate-400">
                      <LogoMark px={14} className="rounded-[4px]" />
                      {c.auto}
                    </span>
                  )}
                  {extras[i]?.(visible)}
                </div>
              </li>
            );
          })}
        </ol>

        {/* replay sits on the start side: the notification card overlaps the end side */}
        <div className="flex h-12 items-center justify-start border-t border-slate-100 px-3">
          <button
            type="button"
            onClick={() => setRun((n) => n + 1)}
            disabled={!done || reduced}
            className={cx(
              "inline-flex h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-slate-500 transition-[opacity,color,background-color] duration-300 hover:bg-slate-100 hover:text-ink-900",
              done && !reduced ? "opacity-100" : "pointer-events-none opacity-0",
            )}
          >
            <RotateCcw className="size-3.5" aria-hidden />
            {c.replay}
          </button>
        </div>
      </div>

      {/* what the owner gets when the bot hands over */}
      <div
        aria-hidden={!done}
        className={cx(
          "absolute -bottom-7 -end-3 hidden w-64 items-start gap-3 rounded-2xl bg-surface p-3.5 text-ink-950 shadow-lift ring-1 ring-line sm:flex xl:-end-10",
          done ? "animate-pop-in [animation-delay:700ms]" : "invisible",
        )}
      >
        <LogoMark px={32} className="rounded-lg" />
        <div className="min-w-0">
          <div className="text-[13px] font-bold">
            <bdi>{c.customer}</bdi> {c.notifyWaiting}
          </div>
          <div className="mt-0.5 truncate text-xs text-slate-500">{c.notifyBody}</div>
        </div>
      </div>
    </figure>
  );
}

function TypingBubble({ label }: { label: string }) {
  return (
    <span role="status" aria-label={label} className="animate-fade-in absolute end-0 top-0 flex items-center gap-1 rounded-2xl rounded-se-md bg-brand-50 px-3.5 py-3">
      <span className="typing-dot size-1.5 rounded-full bg-brand-500" />
      <span className="typing-dot size-1.5 rounded-full bg-brand-500 [animation-delay:0.2s]" />
      <span className="typing-dot size-1.5 rounded-full bg-brand-500 [animation-delay:0.4s]" />
    </span>
  );
}
