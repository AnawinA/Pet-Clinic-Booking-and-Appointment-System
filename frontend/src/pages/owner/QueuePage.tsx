import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { endpoints } from "../../api/endpoints";
import { PetAvatar } from "../../components/PetAvatar";
import { EmptyState, ErrorText, PageHeader, Spinner, StatusBadge } from "../../components/ui";
import { bangkokToday, formatDateTime, formatTime } from "../../lib/format";

export default function QueuePage() {
  const vets = useQuery({ queryKey: ["vets"], queryFn: endpoints.vets.list });
  const [date, setDate] = useState(bangkokToday(0));
  const [vetId, setVetId] = useState("");

  useEffect(() => {
    if (!vetId && vets.data && vets.data.length > 0) setVetId(vets.data[0].id);
  }, [vetId, vets.data]);

  const queue = useQuery({
    queryKey: ["queue", date, vetId],
    queryFn: () => endpoints.queue.live(date, vetId),
    enabled: Boolean(vetId),
    refetchInterval: 3000,
  });

  return (
    <div>
      <PageHeader title="คิวสด" subtitle="อัปเดตอัตโนมัติทุก 3 วินาที" />

      <div className="card mb-5 grid gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="label">วันที่</span>
          <input
            className="input"
            type="date"
            value={date}
            onChange={(event) => setDate(event.target.value)}
          />
        </label>
        <label className="block">
          <span className="label">สัตวแพทย์</span>
          <select className="input" value={vetId} onChange={(event) => setVetId(event.target.value)}>
            {vets.data?.map((vet) => (
              <option key={vet.id} value={vet.id}>
                {vet.full_name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <ErrorText error={queue.error} />
      {queue.isLoading ? <Spinner /> : null}
      {queue.data && queue.data.items.length === 0 ? (
        <EmptyState title="ยังไม่มีคิวในวันนี้" />
      ) : null}

      <div className="space-y-2">
        {queue.data?.items.map((entry, index) => (
          <article key={entry.appointment_id} className="card flex items-center gap-3">
            <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-brand-50 font-bold text-brand-700">
              {index + 1}
            </div>
            <PetAvatar petId={entry.pet_id} name={entry.pet_name} size="sm" />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="truncate font-semibold">{entry.pet_name}</h2>
                <StatusBadge status={entry.status} />
              </div>
              <p className="text-sm text-slate-500">
                {formatTime(entry.slot_start)} น.
                {entry.estimated_start ? ` · คาดว่าเริ่ม ${formatDateTime(entry.estimated_start)} น.` : ""}
              </p>
            </div>
            <span className="text-xs text-slate-400">{entry.ahead_count} คิวก่อนหน้า</span>
          </article>
        ))}
      </div>
    </div>
  );
}
