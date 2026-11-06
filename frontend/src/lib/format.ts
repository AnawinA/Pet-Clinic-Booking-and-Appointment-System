const BANGKOK = "Asia/Bangkok";

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "-";
  return new Intl.DateTimeFormat("th-TH", {
    timeZone: BANGKOK,
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(iso));
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "-";
  return new Intl.DateTimeFormat("th-TH", {
    timeZone: BANGKOK,
    dateStyle: "medium",
  }).format(new Date(`${iso}T00:00:00+07:00`));
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "-";
  return new Intl.DateTimeFormat("th-TH", {
    timeZone: BANGKOK,
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

export function bangkokToday(offsetDays = 0): string {
  const now = new Date();
  now.setDate(now.getDate() + offsetDays);
  return new Intl.DateTimeFormat("en-CA", { timeZone: BANGKOK }).format(now);
}

export function bangkokDateOf(iso: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: BANGKOK }).format(new Date(iso));
}

export function bangkokInputToIso(value: string): string {
  return new Date(`${value}:00+07:00`).toISOString();
}

export function hoursUntil(iso: string): number {
  return (new Date(iso).getTime() - Date.now()) / 3_600_000;
}

export function canOwnerCancel(slotStart: string): boolean {
  return hoursUntil(slotStart) >= 2;
}
