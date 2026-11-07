import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { endpoints } from "../../api/endpoints";
import { TimeInput } from "../../components/TimeInput";
import { pushToast } from "../../components/Toast";
import { EmptyState, ErrorText, Field, PageHeader, Spinner } from "../../components/ui";
import { bangkokToday, formatDate } from "../../lib/format";

export default function ShiftsPage() {
  const queryClient = useQueryClient();
  const vets = useQuery({ queryKey: ["vets"], queryFn: endpoints.vets.list });
  const [date, setDate] = useState(bangkokToday(0));
  const [vetId, setVetId] = useState("");
  const [start, setStart] = useState("09:00");
  const [end, setEnd] = useState("17:00");

  useEffect(() => {
    if (!vetId && vets.data && vets.data.length > 0) setVetId(vets.data[0].id);
  }, [vetId, vets.data]);

  const shifts = useQuery({
    queryKey: ["shifts", date],
    queryFn: () => endpoints.shifts.list(date),
    refetchInterval: 5000,
  });

  const create = useMutation({
    mutationFn: () =>
      endpoints.shifts.create({
        vet_id: vetId,
        shift_date: date,
        start_time: start,
        end_time: end,
      }),
    onSuccess: () => {
      pushToast("success", "สร้างกะแล้ว");
      void queryClient.invalidateQueries({ queryKey: ["shifts"] });
      void queryClient.invalidateQueries({ queryKey: ["availability"] });
    },
  });

  const nextHalfHour = (value: string): string => {
    const [hours, minutes] = value.split(":").map(Number);
    if (!Number.isFinite(hours) || !Number.isFinite(minutes)) return "09:30";
    const total = Math.min(hours * 60 + minutes + 30, 17 * 60);
    return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
  };

  const handleStartChange = (value: string) => {
    setStart(value);
    if (value && end <= value) setEnd(nextHalfHour(value));
  };

  const remove = useMutation({
    mutationFn: (id: string) => endpoints.shifts.remove(id),
    onSuccess: () => {
      pushToast("success", "ลบกะแล้ว");
      void queryClient.invalidateQueries({ queryKey: ["shifts"] });
      void queryClient.invalidateQueries({ queryKey: ["availability"] });
    },
  });

  return (
    <div>
      <PageHeader title="จัดการกะสัตวแพทย์" subtitle="กะต้องอยู่ระหว่าง 09:00–17:00 และไม่ซ้อนกัน" />

      <div className="grid gap-5 lg:grid-cols-[1fr_1.4fr]">
        <form
          className="card space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            create.mutate();
          }}
        >
          <h2 className="font-semibold">สร้างกะใหม่</h2>
          <Field label="วันที่">
            <input
              className="input"
              type="date"
              value={date}
              onChange={(event) => setDate(event.target.value)}
            />
          </Field>
          <Field label="สัตวแพทย์">
            <select className="input" value={vetId} onChange={(event) => setVetId(event.target.value)}>
              {vets.data?.map((vet) => (
                <option key={vet.id} value={vet.id}>
                  {vet.full_name}
                </option>
              ))}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="เริ่ม">
              <TimeInput value={start} max="16:30" onChange={handleStartChange} />
            </Field>
            <Field label="สิ้นสุด">
              <TimeInput value={end} min={nextHalfHour(start)} max="17:00" onChange={setEnd} />
            </Field>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            เลือกเวลาเป็นรอบละ 30 นาที ระหว่าง 09:00–17:00 น.
          </p>
          <ErrorText error={create.error} />
          <button type="submit" className="btn-primary w-full" disabled={create.isPending || !vetId}>
            {create.isPending ? "กำลังสร้าง..." : "สร้างกะ"}
          </button>
        </form>

        <section>
          <h2 className="mb-2 font-semibold">กะวันที่ {formatDate(date)}</h2>
          <ErrorText error={shifts.error} />
          {shifts.isLoading ? <Spinner /> : null}
          {shifts.data && shifts.data.length === 0 ? (
            <EmptyState title="ยังไม่มีกะในวันนี้" />
          ) : null}
          <div className="space-y-2">
            {shifts.data?.map((shift) => (
              <article key={shift.id} className="card flex items-center justify-between gap-3">
                <div>
                  <p className="font-medium">{shift.vet_name}</p>
                  <p className="text-sm text-slate-500">
                    {shift.start_time}–{shift.end_time} น.
                  </p>
                </div>
                <button
                  type="button"
                  className="btn-danger"
                  disabled={remove.isPending}
                  onClick={() => remove.mutate(shift.id)}
                >
                  ลบ
                </button>
              </article>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
