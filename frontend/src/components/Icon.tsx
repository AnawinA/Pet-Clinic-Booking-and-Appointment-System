import type { ReactNode } from "react";

export type IconName =
  | "calendar"
  | "plus"
  | "paw"
  | "clock"
  | "bell"
  | "clipboard"
  | "shield"
  | "users"
  | "userPlus"
  | "activity"
  | "sun"
  | "moon"
  | "logout"
  | "sparkles"
  | "stethoscope";

const PATHS: Record<IconName, ReactNode> = {
  calendar: (
    <>
      <rect x="3" y="4.5" width="18" height="16" rx="2.5" />
      <path d="M8 2.5v4M16 2.5v4M3 9.5h18" />
    </>
  ),
  plus: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v8M8 12h8" />
    </>
  ),
  paw: (
    <>
      <circle cx="7" cy="8" r="1.8" />
      <circle cx="12" cy="6.2" r="1.8" />
      <circle cx="17" cy="8" r="1.8" />
      <circle cx="19" cy="12.5" r="1.6" />
      <circle cx="5" cy="12.5" r="1.6" />
      <path d="M12 11.5c-2.8 0-5 2.1-5 4.4 0 2 1.5 3.3 3.4 3.3 1 0 1.6-.4 1.6-.4s.6.4 1.6.4c1.9 0 3.4-1.3 3.4-3.3 0-2.3-2.2-4.4-5-4.4Z" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  bell: (
    <>
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.7 21a2 2 0 0 1-3.4 0" />
    </>
  ),
  clipboard: (
    <>
      <rect x="5" y="4" width="14" height="17" rx="2.5" />
      <path d="M9 4V3h6v1M9 10h6M9 14h6" />
    </>
  ),
  shield: (
    <>
      <path d="m12 3 7 3v6c0 4.5-3 8-7 9-4-1-7-4.5-7-9V6l7-3Z" />
      <path d="m9 12 2 2 4-4" />
    </>
  ),
  users: (
    <>
      <circle cx="9" cy="8" r="3" />
      <path d="M3 20c0-3 2.7-5 6-5s6 2 6 5" />
      <path d="M17 5a3 3 0 0 1 0 6M21 20c0-2.5-1.7-4.5-4-5" />
    </>
  ),
  userPlus: (
    <>
      <circle cx="9" cy="8" r="4" />
      <path d="M3 21c0-3.3 2.7-6 6-6M19 8v6M16 11h6" />
    </>
  ),
  activity: (
    <>
      <path d="M3 12h4l3-8 4 16 3-8h4" />
    </>
  ),
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </>
  ),
  moon: (
    <>
      <path d="M21 12.8A8.5 8.5 0 1 1 11.2 3 7 7 0 0 0 21 12.8Z" />
    </>
  ),
  logout: (
    <>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <path d="m16 17 5-5-5-5M21 12H9" />
    </>
  ),
  sparkles: (
    <>
      <path d="m12 3 1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8L12 3Z" />
      <path d="M19 15v4M17 17h4M5 3v3M3.5 4.5h3" />
    </>
  ),
  stethoscope: (
    <>
      <path d="M6 3v5a4 4 0 0 0 8 0V3M6 3H4.5M14 3h1.5" />
      <path d="M10 12v2a5 5 0 0 0 10 0v-2" />
      <circle cx="20" cy="9" r="2" />
    </>
  ),
};

export function Icon({
  name,
  className = "h-5 w-5",
}: {
  name: IconName;
  className?: string;
}) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      {PATHS[name]}
    </svg>
  );
}
