import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { endpoints } from "../../api/endpoints";
import { useAuth } from "../../auth/AuthContext";
import { PetAvatar } from "../../components/PetAvatar";
import { EmptyState, ErrorText, PageHeader, Spinner, StatusBadge } from "../../components/ui";
import { bangkokToday, formatDateTime, formatTime } from "../../lib/format";

export default function SchedulePage() {
  const { user } = useAuth();
  const [date, setDate] = useState(bangkokToday(0));

  const schedule = useQuery({
    queryKey: ["schedule", date, user?.id],
    queryFn: () => endpoints.schedule.list(date, user!.id),
    enabled: Boolean(user),
    refetchInterval: 5000,
  });

  return (
    <div>
      <PageHeader
        title="ตารางงานของฉัน"
        subtitle="อัปเดตอัตโนมัติทุก 5 วินาที"
        actions={
          <input
            className="input w-auto"
            type="date"
            value={date}
            onChange={(event) => setDate(event.target.value)}
          />
        }
      />

      <ErrorText error={schedule.error} />
      {schedule.isLoading ? <Spinner /> : null}
      {schedule.data && schedule.data.items.length === 0 ? (
        <EmptyState title="ไม่มีนัดในวันนี้" hint="เลือกวันอื่นเพื่อดูตารางงาน" />
      ) : null}

      <div className="space-y-2">
        {schedule.data?.items.map((entry) => (
          <article key={entry.appointment_id} className="card">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-start gap-3">
                <PetAvatar petId={entry.pet_id} name={entry.pet_name} size="md" />
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="font-semibold">{entry.pet_name}</h2>
                  <StatusBadge status={entry.status} />
                </div>
                <p className="text-sm text-slate-500">
                  {formatTime(entry.slot_start)}–{formatTime(entry.slot_end)} น. · เจ้าของ{" "}
                  {entry.owner_name}
                </p>
                <p className="mt-1 text-sm text-slate-600">อาการ: {entry.symptoms}</p>
                {entry.estimated_start ? (
                  <p className="mt-1 text-xs text-brand-700">
                    คาดว่าเริ่ม {formatDateTime(entry.estimated_start)} น.
                  </p>
                  ) : null}
                </div>
              </div>
              <Link to={`/vet/cases/${entry.appointment_id}`} className="btn-secondary shrink-0">
                เปิดเคส
              </Link>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
