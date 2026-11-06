import { useTheme } from "../theme/ThemeContext";
import { Icon } from "./Icon";

export function ThemeToggle({
  variant = "default",
  className = "",
}: {
  variant?: "default" | "glass";
  className?: string;
}) {
  const { theme, toggleTheme } = useTheme();
  const dark = theme === "dark";
  const label = "สลับโหมดสว่างและมืด";
  const skin =
    variant === "glass"
      ? "border-white/25 bg-white/10 text-white backdrop-blur hover:bg-white/20"
      : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-600 dark:hover:text-white";

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={label}
      aria-pressed={dark}
      title={dark ? "เปลี่ยนเป็นโหมดสว่าง" : "เปลี่ยนเป็นโหมดมืด"}
      className={`inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${skin} ${className}`}
    >
      <Icon name={dark ? "sun" : "moon"} className="h-[18px] w-[18px]" />
    </button>
  );
}
