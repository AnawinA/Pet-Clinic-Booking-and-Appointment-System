import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Icon } from "./Icon";
import { ThemeToggle } from "./ThemeToggle";

interface AuthLayoutProps {
  eyebrow: string;
  title: string;
  subtitle: string;
  headline: ReactNode;
  description: string;
  features: string[];
  children: ReactNode;
  footer: ReactNode;
}

function BrandMark() {
  return (
    <Link to="/" className="flex items-center gap-3 text-white">
      <span className="grid h-11 w-11 place-items-center rounded-2xl bg-white/15 ring-1 ring-inset ring-white/25 backdrop-blur">
        <Icon name="paw" className="h-5 w-5" />
      </span>
      <span>
        <span className="block text-lg font-bold leading-tight">PetCare</span>
        <span className="block text-xs text-white/70">Clinic &amp; Appointment</span>
      </span>
    </Link>
  );
}

export function AuthLayout({
  eyebrow,
  title,
  subtitle,
  headline,
  description,
  features,
  children,
  footer,
}: AuthLayoutProps) {
  return (
    <div className="min-h-screen bg-slate-50 transition-colors dark:bg-slate-950 lg:grid lg:grid-cols-[1.05fr_1fr]">
      <aside className="relative hidden overflow-hidden lg:block">
        <img
          src="/login-hero.jpg"
          alt="ลูกสุนัขโกลเดนรีทรีฟเวอร์นั่งคาบดอกไม้"
          className="absolute inset-0 h-full w-full object-cover object-[center_35%]"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-slate-950/90 via-slate-950/45 to-slate-950/15" />

        <div className="relative flex h-full flex-col justify-between p-10 text-white xl:p-14">
          <BrandMark />

          <div className="max-w-lg">
            <span className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-medium ring-1 ring-inset ring-white/20 backdrop-blur">
              <Icon name="paw" className="h-3.5 w-3.5" />
              PetCare Clinic
            </span>
            <h2 className="mt-5 text-3xl font-bold leading-snug xl:text-4xl">{headline}</h2>
            <p className="mt-3 max-w-md text-sm leading-relaxed text-white/75">{description}</p>

            <ul className="mt-8 space-y-3 text-sm text-white/85">
              {features.map((feature) => (
                <li key={feature} className="flex items-start gap-3">
                  <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-brand-500/25 text-xs text-brand-100 ring-1 ring-inset ring-white/20">
                    ✓
                  </span>
                  <span>{feature}</span>
                </li>
              ))}
            </ul>
          </div>

          <a
            href="https://unsplash.com/license"
            target="_blank"
            rel="noreferrer"
            className="w-fit text-[11px] text-white/45 transition hover:text-white/70"
          >
            ภาพประกอบจาก Unsplash — ใช้ฟรี
          </a>
        </div>
      </aside>

      <div className="relative h-44 overflow-hidden lg:hidden">
        <img
          src="/login-hero.jpg"
          alt=""
          className="absolute inset-0 h-full w-full object-cover object-[center_30%]"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-slate-950/85 via-slate-950/35 to-transparent" />
        <div className="absolute inset-x-0 bottom-0 flex items-end justify-between p-5 text-white">
          <div>
            <p className="text-xl font-bold leading-tight">PetCare Clinic</p>
            <p className="mt-0.5 text-xs text-white/75">ดูแลทุกก้าวของสัตว์เลี้ยงคุณ</p>
          </div>
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-white/15 ring-1 ring-inset ring-white/25 backdrop-blur">
            <Icon name="paw" className="h-4 w-4" />
          </span>
        </div>
      </div>

      <div className="absolute right-4 top-4 z-30 sm:right-6 sm:top-6">
        <ThemeToggle />
      </div>

      <main className="relative flex items-center justify-center overflow-hidden px-5 py-10 sm:px-8 lg:py-16">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-brand-200/40 blur-3xl dark:bg-brand-500/10"
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -bottom-24 -left-24 h-72 w-72 rounded-full bg-emerald-100/50 blur-3xl dark:bg-emerald-500/5"
        />

        <div className="relative w-full max-w-md">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-700 dark:text-brand-300">
            {eyebrow}
          </p>
          <h1 className="mt-2 text-2xl font-bold tracking-tight text-slate-900 dark:text-white sm:text-3xl">
            {title}
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-slate-500 dark:text-slate-400">{subtitle}</p>

          <div className="mt-7 rounded-2xl border border-slate-200 bg-white p-5 shadow-xl shadow-slate-200/60 transition-colors dark:border-slate-800 dark:bg-slate-900/90 dark:shadow-black/30 sm:p-6">
            {children}
          </div>

          <div className="mt-6 text-center text-sm text-slate-600 dark:text-slate-400">{footer}</div>

          <p className="mt-4 text-center text-[11px] text-slate-400 dark:text-slate-500">
            🔒 ข้อมูลของคุณถูกจัดเก็บอย่างปลอดภัย
          </p>
        </div>
      </main>
    </div>
  );
}
