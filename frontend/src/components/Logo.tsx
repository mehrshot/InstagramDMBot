import { useI18n } from "../i18n";
import { cx } from "./ui";

/**
 * The Javab logo: the mascot on a soft lavender app-icon tile (corners already rounded in the file).
 * `px` is the rendered size, so the browser picks the smallest file that is still sharp.
 */
export function LogoMark({ px = 36, className, alt = "" }: { px?: number; className?: string; alt?: string }) {
  return (
    <img
      src="/brand/javab-mascot-128.png"
      srcSet="/brand/javab-mascot-128.png 128w, /brand/javab-mascot-192.png 192w, /brand/javab-mascot-512.png 512w"
      sizes={`${px}px`}
      width={px}
      height={px}
      alt={alt}
      decoding="async"
      className={cx("aspect-square shrink-0 rounded-[24%]", className)}
      style={{ width: px, height: px }}
    />
  );
}

/** Mark + name. `tone` is the surface it sits on. */
export function Logo({ tone = "light", className, markClassName }: { tone?: "light" | "dark"; className?: string; markClassName?: string }) {
  const { t } = useI18n();
  return (
    <span className={cx("inline-flex items-center gap-2.5", className)}>
      <LogoMark className={markClassName} />
      <span className={cx("text-xl font-black", tone === "dark" ? "text-white" : "text-ink-900")}>{t.appName}</span>
    </span>
  );
}
