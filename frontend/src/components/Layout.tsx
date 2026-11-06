import { useQuery } from "@tanstack/react-query";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { endpoints } from "../api/endpoints";
import type { UserRole } from "../api/types";
import { homeFor, useAuth } from "../auth/AuthContext";
import { Icon } from "./Icon";
import type { IconName } from "./Icon";
import { ThemeToggle } from "./ThemeToggle";

const NAV: Record<UserRole, { to: string; label: string; icon: IconName }[]> = {
  OWNER: [
    { to: "/owner/appointments", label: "นัดของฉัน", icon: "calendar" },
    { to: "/owner/book", label: "จองนัด", icon: "plus" },
    { to: "/owner/pets", label: "สัตว์เลี้ยง", icon: "paw" },
    { to: "/owner/queue", label: "คิวสด", icon: "clock" },
    { to: "/owner/notifications", label: "แจ้งเตือน", icon: "bell" },
  ],
  VET: [
    { to: "/vet/schedule", label: "ตารางงาน", icon: "calendar" },
    { to: "/vet/notifications", label: "แจ้งเตือน", icon: "bell" },
  ],
  STAFF: [
    { to: "/staff/board", label: "กระดานนัด", icon: "clipboard" },
    { to: "/staff/shifts", label: "จัดการกะ", icon: "clock" },
    { to: "/staff/reschedule-requests", label: "คำขอปรับเวลา", icon: "activity" },
    { to: "/staff/audit", label: "Audit Log", icon: "shield" },
    { to: "/staff/accounts", label: "สร้างบัญชี", icon: "userPlus" },
    { to: "/staff/notifications", label: "แจ้งเตือน", icon: "bell" },
  ],
};

const ROLE_LABELS: Record<UserRole, string> = {
  OWNER: "เจ้าของสัตว์เลี้ยง",
  VET: "สัตวแพทย์",
  STAFF: "เจ้าหน้าที่",
};

const HOME_COPY: Record<
  UserRole,
  { title: string; subtitle: string; hint: string; icon: IconName }
> = {
  OWNER: {
    title: "ภาพรวมนัดหมายของคุณ",
    subtitle: "ดูนัดที่กำลังจะมาถึง จัดการข้อมูลสัตว์เลี้ยง และติดตามคิวได้จากที่เดียว",
    hint: "จองนัดได้ตลอด 24 ชม.",
    icon: "calendar",
  },
  VET: {
    title: "ตารางงานวันนี้พร้อมแล้ว",
    subtitle: "ตรวจเคส บันทึกการรักษา และติดตามผู้ป่วยในความดูแลของคุณ",
    hint: "อัปเดตทุก 5 วินาที",
    icon: "stethoscope",
  },
  STAFF: {
    title: "ทุกเคสอยู่ในมือคุณ",
    subtitle: "จัดการกระดานนัด ตรวจคำขอปรับเวลา และดูแลทีมงานจากศูนย์กลางเดียว",
    hint: "ภาพรวมทั้งคลินิก",
    icon: "clipboard",
  },
};

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "สวัสดีตอนเช้า";
  if (hour < 17) return "สวัสดีตอนบ่าย";
  return "สวัสดีตอนเย็น";
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "P";
  if (parts.length === 1) return parts[0].slice(0, 1).toUpperCase();
  return `${parts[0].slice(0, 1)}${parts[parts.length - 1].slice(0, 1)}`.toUpperCase();
}

function WelcomeBanner({ role, fullName }: { role: UserRole; fullName: string }) {
  const copy = HOME_COPY[role];
  const today = new Intl.DateTimeFormat("th-TH", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(new Date());

  return (
    <section className="relative mb-6 overflow-hidden rounded-3xl border border-brand-500/20 bg-gradient-to-br from-brand-700 via-brand-600 to-emerald-800 p-5 text-white shadow-xl shadow-brand-900/20 sm:p-7 dark:border-brand-400/15 dark:from-brand-800 dark:via-slate-900 dark:to-slate-950">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-20 [background-image:radial-gradient(circle_at_1px_1px,white_1px,transparent_0)] [background-size:22px_22px]"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-12 -top-20 h-56 w-56 rounded-full border-[26px] border-white/10"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-24 right-24 h-48 w-48 rounded-full bg-emerald-300/20 blur-3xl"
      />

      <div className="relative flex items-start justify-between gap-4">
        <div className="flex items-start gap-4">
          <span className="hidden h-12 w-12 shrink-0 place-items-center rounded-2xl bg-white/15 ring-1 ring-inset ring-white/25 backdrop-blur sm:grid">
            <Icon name={copy.icon} className="h-6 w-6" />
          </span>
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-brand-100/80">
              {greeting()} · {today}
            </p>
            <h2 className="mt-1 text-xl font-bold tracking-tight sm:text-2xl">{copy.title}</h2>
            <p className="mt-1 max-w-xl text-sm leading-relaxed text-brand-50/85">
              {fullName} — {copy.subtitle}
            </p>
          </div>
        </div>
        <span className="hidden shrink-0 items-center gap-1.5 rounded-full bg-white/10 px-3 py-1 text-[11px] font-medium text-white/85 ring-1 ring-inset ring-white/20 backdrop-blur md:inline-flex">
          <Icon name="sparkles" className="h-3.5 w-3.5" />
          {copy.hint}
        </span>
      </div>
    </section>
  );
}

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const { data: unread } = useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: () => endpoints.notifications.list({ unreadOnly: true, limit: 50 }),
    refetchInterval: 5000,
    enabled: Boolean(user),
  });

  if (!user) return null;

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  const isHome = location.pathname === homeFor(user.role);

  return (
    <div className="relative min-h-screen bg-slate-50 text-slate-900 transition-colors dark:bg-slate-950 dark:text-slate-100">
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(75%_55%_at_50%_0%,rgba(18,160,106,0.11),transparent)] dark:bg-[radial-gradient(75%_55%_at_50%_0%,rgba(16,185,129,0.10),transparent)]"
      />

      <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/80 backdrop-blur-xl dark:border-slate-800 dark:bg-slate-950/80">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <div className="flex min-h-16 items-center justify-between gap-3 py-2">
            <button
              type="button"
              onClick={() => navigate(homeFor(user.role))}
              className="group flex items-center gap-3 rounded-xl text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              aria-label="กลับหน้าหลัก PetCare"
            >
              <span className="grid h-10 w-10 place-items-center rounded-2xl bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-md shadow-brand-600/25 ring-1 ring-inset ring-white/20">
                <Icon name="paw" className="h-5 w-5" />
              </span>
              <span>
                <span className="block text-sm font-bold leading-tight tracking-tight">PetCare</span>
                <span className="mt-0.5 block text-[11px] font-medium text-slate-500 dark:text-slate-400">
                  {ROLE_LABELS[user.role]}
                </span>
              </span>
            </button>

            <div className="flex items-center gap-2">
              <div className="hidden items-center gap-2.5 rounded-2xl border border-slate-200 bg-white/70 py-1.5 pl-1.5 pr-3 shadow-sm shadow-slate-200/40 dark:border-slate-800 dark:bg-slate-900/70 dark:shadow-none md:flex">
                <span className="grid h-8 w-8 place-items-center rounded-xl bg-brand-50 text-[11px] font-bold text-brand-700 dark:bg-brand-500/15 dark:text-brand-200">
                  {initials(user.full_name)}
                </span>
                <span className="max-w-[12rem]">
                  <span className="block truncate text-xs font-semibold leading-tight">
                    {user.full_name}
                  </span>
                  <span className="block text-[10px] text-slate-500 dark:text-slate-400">
                    {ROLE_LABELS[user.role]}
                  </span>
                </span>
              </div>

              <ThemeToggle />

              <button
                type="button"
                onClick={handleLogout}
                aria-label="ออกจากระบบ"
                title="ออกจากระบบ"
                className="inline-flex h-9 items-center gap-2 rounded-xl border border-slate-200 bg-white px-2.5 text-xs font-semibold text-rose-600 transition hover:border-rose-200 hover:bg-rose-50 dark:border-slate-700 dark:bg-slate-900 dark:text-rose-300 dark:hover:border-rose-500/30 dark:hover:bg-rose-500/10 sm:px-3"
              >
                <Icon name="logout" className="h-4 w-4" />
                <span className="hidden sm:inline">ออกจากระบบ</span>
              </button>
            </div>
          </div>

          <nav
            aria-label="เมนูหลัก"
            className="-mx-1 flex items-center gap-1 overflow-x-auto pb-3 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
          >
            {NAV[user.role].map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `flex shrink-0 items-center gap-2 whitespace-nowrap rounded-xl px-3 py-2 text-sm transition ${
                    isActive
                      ? "bg-brand-50 font-semibold text-brand-700 shadow-sm shadow-brand-600/10 dark:bg-brand-500/15 dark:text-brand-200"
                      : "text-slate-500 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white"
                  }`
                }
              >
                <Icon name={item.icon} className="h-4 w-4" />
                {item.label}
                {item.to.endsWith("/notifications") && unread && unread.length > 0 ? (
                  <span className="ml-0.5 rounded-full bg-rose-500 px-1.5 text-[10px] font-bold leading-4 text-white">
                    {unread.length}
                  </span>
                ) : null}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8">
        {isHome ? <WelcomeBanner role={user.role} fullName={user.full_name} /> : null}
        <Outlet />
      </main>

      <footer className="mx-auto max-w-6xl px-4 pb-8 text-center text-[11px] text-slate-400 dark:text-slate-600">
        PetCare Clinic · ดูแลทุกก้าวของสัตว์เลี้ยงคุณ
      </footer>
    </div>
  );
}
