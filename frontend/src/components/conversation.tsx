import type { ReactNode } from "react";
import { Bot, FileIcon, Image, Mic, Paperclip, Smile, UserRound, Video } from "lucide-react";
import type { Message } from "../api/types";
import { useI18n } from "../i18n";
import { PostCard, sharedPostUrl } from "./PostCard";
import { customerName } from "../lib/format";
import { Badge, cx } from "./ui";

/** Pause set "until resumed by hand" is stored as ~10 years ahead. */
export function isIndefinitePause(until: string | null): boolean {
  return !!until && new Date(until).getTime() - Date.now() > 365 * 24 * 3600 * 1000;
}

export function useCustomerName() {
  const { t, f } = useI18n();
  return (username: string | null | undefined, igsid: string) => customerName(username, igsid, t, f);
}

export function Avatar({ name, className }: { name: string; className?: string }) {
  const letter = name.replace(/^[^\p{L}\p{N}]+/u, "").charAt(0).toUpperCase() || "?";
  return (
    <span className={cx("flex size-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand-100 to-pink-100 font-semibold text-brand-700", className)}>
      {letter}
    </span>
  );
}

const MARKER = /\[([a-z_]+)\]/g;

/** Message text with `[image]`/`[audio]`… markers (media the customer sent) shown as chips. */
export function MessageText({ text }: { text: string }) {
  const { t } = useI18n();
  const labels: Record<string, [string, ReactNode]> = {
    image: [t.inbox.image, <Image key="i" className="size-3.5" />],
    audio: [t.inbox.audio, <Mic key="a" className="size-3.5" />],
    video: [t.inbox.video, <Video key="v" className="size-3.5" />],
    ig_reel: [t.inbox.video, <Video key="r" className="size-3.5" />],
    reel: [t.inbox.video, <Video key="r2" className="size-3.5" />],
    file: [t.inbox.attachment, <FileIcon key="f" className="size-3.5" />],
    sticker: [t.inbox.sticker, <Smile key="s" className="size-3.5" />],
    animated_image: [t.inbox.sticker, <Smile key="s2" className="size-3.5" />],
  };

  const parts: ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(MARKER)) {
    const idx = m.index ?? 0;
    if (idx > last) parts.push(text.slice(last, idx));
    const [label, icon] = labels[m[1]] ?? [m[1], <Paperclip key="p" className="size-3.5" />];
    parts.push(
      <span key={idx} className="mx-0.5 inline-flex items-center gap-1 rounded-md bg-black/5 px-1.5 py-0.5 align-middle text-xs">
        {icon}
        {label}
      </span>,
    );
    last = idx + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return <>{parts}</>;
}

/** One-line preview for lists (markers become labels). */
export function useMessagePreview() {
  const { t } = useI18n();
  const labels: Record<string, string> = { image: t.inbox.image, audio: t.inbox.audio, video: t.inbox.video, sticker: t.inbox.sticker, file: t.inbox.attachment };
  return (text: string) => text.replace(MARKER, (_, k: string) => `(${labels[k] ?? k})`).replace(/\s+/g, " ").trim();
}

/**
 * customer: start side (right in RTL), neutral
 * bot:      end side, brand colour + bot icon
 * owner:    end side, different colour + "You" label
 */
export function MessageBubble({ message }: { message: Message }) {
  const { t, f } = useI18n();
  const mine = message.sender !== "customer";
  const post = message.sender === "bot" ? sharedPostUrl(message.text) : null;

  return (
    <div className={cx("flex flex-col gap-1", mine ? "items-end" : "items-start")}>
      <div className={cx("flex max-w-[85%] items-end gap-2 sm:max-w-[70%]", mine && "flex-row-reverse")}>
        {message.sender === "bot" && (
          <span className="mb-1 flex size-6 shrink-0 items-center justify-center rounded-full bg-brand-100 text-brand-700">
            <Bot className="size-3.5" />
          </span>
        )}
        {message.sender === "owner" && (
          <span className="mb-1 flex size-6 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
            <UserRound className="size-3.5" />
          </span>
        )}
        {post ? (
          <PostCard post={{ permalink: post }} />
        ) : (
          <div
            className={cx(
              "user-text rounded-2xl px-4 py-2.5 text-sm leading-7",
              message.sender === "customer" && "rounded-ss-sm bg-slate-100 text-slate-800",
              message.sender === "bot" && "rounded-se-sm bg-brand-600 text-white",
              message.sender === "owner" && "rounded-se-sm bg-emerald-600 text-white",
            )}
          >
            <MessageText text={message.text} />
          </div>
        )}
      </div>
      <div className={cx("flex items-center gap-2 text-[11px] text-slate-400", mine ? "me-8" : "ms-1")}>
        {message.sender === "owner" && <span className="font-medium text-emerald-700">{t.inbox.senderOwner}</span>}
        {message.sender === "bot" && <span>{t.inbox.senderBot}</span>}
        <span title={f.dateTime(message.created_at)}>{f.smart(message.created_at)}</span>
        {message.unanswered && <Badge tone="amber">{t.inbox.botDidntKnow}</Badge>}
      </div>
    </div>
  );
}
