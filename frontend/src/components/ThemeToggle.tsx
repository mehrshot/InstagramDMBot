import { Moon, Sun } from "lucide-react";
import { useI18n } from "../i18n";
import { useTheme } from "../theme";
import { cx } from "./ui";

/**
 * Light/dark switch. The moon shows in light mode and the sun in dark mode; they swap with a
 * quick rotate. `label` adds the action as text (for menus); otherwise it's an icon button.
 */
export default function ThemeToggle({ className, label }: { className?: string; label?: boolean }) {
  const { t } = useI18n();
  const { resolved, toggle } = useTheme();
  const dark = resolved === "dark";
  const action = dark ? t.theme.toLight : t.theme.toDark;
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={label ? undefined : action}
      title={label ? undefined : action}
      className={cx("inline-flex items-center gap-2.5 transition-colors", className)}
    >
      <span aria-hidden className="relative inline-flex size-[18px] shrink-0">
        <Moon
          className={cx(
            "absolute inset-0 size-[18px] transition-[transform,opacity] duration-300 ease-[var(--ease-out-soft)]",
            dark ? "rotate-90 scale-50 opacity-0" : "rotate-0 scale-100 opacity-100",
          )}
        />
        <Sun
          className={cx(
            "absolute inset-0 size-[18px] transition-[transform,opacity] duration-300 ease-[var(--ease-out-soft)]",
            dark ? "rotate-0 scale-100 opacity-100" : "-rotate-90 scale-50 opacity-0",
          )}
        />
      </span>
      {label && <span>{dark ? t.theme.lightMode : t.theme.darkMode}</span>}
    </button>
  );
}
