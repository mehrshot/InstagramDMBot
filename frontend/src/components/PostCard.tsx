import { ExternalLink, Images } from "lucide-react";
import { useI18n } from "../i18n";
import { cx } from "./ui";

/** How the backend records a shared post in a conversation: "[پست] <permalink>". */
export const POST_MARKER = "[پست]";

export function sharedPostUrl(text: string): string | null {
  return text.startsWith(POST_MARKER) ? text.slice(POST_MARKER.length).trim() : null;
}

type Post = { permalink: string; caption?: string | null; preview_url?: string | null };

/** An Instagram post the bot sent: in the DM the customer sees the real post card. */
export function PostCard({ post, className }: { post: Post; className?: string }) {
  const { t } = useI18n();
  return (
    <a
      href={post.permalink}
      target="_blank"
      rel="noopener noreferrer"
      className={cx(
        "flex w-64 max-w-full items-center gap-3 rounded-xl border border-slate-200 bg-white p-2 text-start shadow-sm transition hover:border-brand-300",
        className,
      )}
    >
      {post.preview_url ? (
        <img src={post.preview_url} alt="" className="size-14 shrink-0 rounded-lg object-cover" loading="lazy" />
      ) : (
        <span className="flex size-14 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-brand-100 to-pink-100 text-brand-700">
          <Images className="size-6" />
        </span>
      )}
      <span className="min-w-0 flex-1">
        <span className="block text-xs font-semibold text-slate-800">{t.posts.cardTitle}</span>
        {post.caption && <span className="user-text line-clamp-2 text-xs text-slate-500">{post.caption}</span>}
        <span className="mt-0.5 inline-flex items-center gap-1 text-[11px] font-medium text-brand-600">
          {t.posts.view}
          <ExternalLink className="size-3" />
        </span>
      </span>
    </a>
  );
}
