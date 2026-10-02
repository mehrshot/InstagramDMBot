import { useState } from "react";
import { Check, Copy } from "lucide-react";
import type { Channel } from "../api/types";
import { useI18n } from "../i18n";
import { ChannelMark } from "./site/channels";
import { Button, cx } from "./ui";

/** The channel's logo in its own colour, for conversation lists and headers. */
export function ChannelIcon({ channel, className }: { channel: Channel; className?: string }) {
  const tone = channel === "telegram" ? "text-sky-500" : "text-pink-600";
  return <ChannelMark channel={channel} className={cx("size-3.5", tone, className)} />;
}

/** "تلگرام" / "اکانت تلگرام شما" / "اینستاگرام" for a conversation. */
export function useChannelLabel() {
  const { t } = useI18n();
  return (channel: Channel, business?: boolean) => {
    if (channel === "telegram") return business ? t.launch.channel.business : t.launch.channel.telegram;
    return t.launch.channel.instagram;
  };
}

export function CopyButton({ value, size = "sm" }: { value: string; size?: "sm" | "md" }) {
  const { t } = useI18n();
  const [done, setDone] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      // older browsers: select the text so the owner can copy it by hand
      window.prompt("", value);
    }
    setDone(true);
    setTimeout(() => setDone(false), 1800);
  }
  return (
    <Button size={size} variant="secondary" icon={done ? <Check className="size-4 text-emerald-600" /> : <Copy className="size-4" />} onClick={copy}>
      {done ? t.launch.telegram.copied : t.launch.telegram.copy}
    </Button>
  );
}
