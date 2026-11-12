import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { endpoints } from "../../api/endpoints";
import type { BulkShiftCreatePayload, BulkShiftPreview } from "../../api/types";
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

  const [bulkStartDate, setBulkStartDate] = useState(bangkokToday(0));
  const [bulkEndDate, setBulkEndDate] = useState(bangkokToday(6));
  const [bulkStart, setBulkStart] = useState("09:00");
  const [bulkEnd, setBulkEnd] = useState("17:00");
  const [bulkAllVets, setBulkAllVets] = useState(true);
  const [bulkVetIds, setBulkVetIds] = useState<string[]>([]);
  const [bulkPreview, setBulkPreview] = useState<BulkShiftPreview | null>(null);
  const [bulkDialogOpen, setBulkDialogOpen] = useState(false);

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

  const bulkPayload = (): BulkShiftCreatePayload => ({
    start_date: bulkStartDate,
    end_date: bulkEndDate,
    start_time: bulkStart,
    end_time: bulkEnd,
    vet_ids: bulkAllVets ? [] : bulkVetIds,
    all_vets: bulkAllVets,
  });

  const bulkPreviewMutation = useMutation({
    mutationFn: endpoints.shifts.bulkPreview,
    onSuccess: (preview) => {
      setBulkPreview(preview);
      setBulkDialogOpen(true);
    },
    onError: (error) => {
      pushToast(
        "error",
        error instanceof Error ? error.message : "ไม่สามารถตรวจสอบกะที่จะแทนที่ได้",
      );
    },
  });

  const bulkCreate = useMutation({
    mutationFn: endpoints.shifts.bulkCreate,
    onSuccess: (result) => {
      pushToast(
        "success",
        `สร้าง ${result.created} กะแล้ว${result.replaced ? ` (แทนที่ ${result.replaced} กะเดิม)` : ""}`,
      );
      setBulkDialogOpen(false);
      setBulkPreview(null);
      void queryClient.invalidateQueries({ queryKey: ["shifts"] });
      void queryClient.invalidateQueries({ queryKey: ["availability"] });
    },
  });

  const closeBulkDialog = () => {
    setBulkDialogOpen(false);
    setBulkPreview(null);
    bulkCreate.reset();
  };

  const bulkSelectedCount = bulkAllVets ? (vets.data?.length ?? 0) : bulkVetIds.length;
  const bulkInvalidRange = bulkEndDate < bulkStartDate;
  const bulkBlocked = (bulkPreview?.blocked_shifts.length ?? 0) > 0;

  const toggleBulkVet = (id: string, checked: boolean) => {
    setBulkVetIds((current) =>
      checked ? [...new Set([...current, id])] : current.filter((value) => value !== id),
    );
  };

  return (
    <div>
      <PageHeader title="จัดการกะสัตวแพทย์" subtitle="กะต้องอยู่ระหว่าง 09:00–17:00 และไม่ซ้อนกัน" />

      <form
        className="card mb-5 space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          bulkPreviewMutation.mutate(bulkPayload());
        }}
      >
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h2 className="font-semibold">สร้างกะแบบพิเศษ</h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              สร้างกะช่วงวันที่เริ่มต้นถึงสิ้นสุดให้สัตวแพทย์หลายคนได้ในครั้งเดียว
            </p>
          </div>
          <span className="rounded-full bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-700">
            หลายวัน / หลายคน
          </span>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="วันที่เริ่ม">
            <input
              className="input"
              type="date"
              value={bulkStartDate}
              onChange={(event) => {
                const value = event.target.value;
                setBulkStartDate(value);
                if (bulkEndDate < value) setBulkEndDate(value);
              }}
            />
          </Field>
          <Field label="วันที่สิ้นสุด">
            <input
              className="input"
              type="date"
              min={bulkStartDate}
              value={bulkEndDate}
              onChange={(event) => setBulkEndDate(event.target.value)}
            />
          </Field>
          <Field label="เวลาเริ่ม">
            <TimeInput
              value={bulkStart}
              max="16:30"
              onChange={(value) => {
                setBulkStart(value);
                if (value && bulkEnd <= value) setBulkEnd(nextHalfHour(value));
              }}
            />
          </Field>
          <Field label="เวลาสิ้นสุด">
            <TimeInput
              value={bulkEnd}
              min={nextHalfHour(bulkStart)}
              max="17:00"
              onChange={setBulkEnd}
            />
          </Field>
        </div>

        <div>
          <p className="mb-2 text-sm font-medium">สัตวแพทย์</p>
          <label className="mb-2 flex items-center gap-2 text-sm font-semibold text-brand-700">
            <input
              type="checkbox"
              checked={bulkAllVets}
              onChange={(event) => {
                const checked = event.target.checked;
                setBulkAllVets(checked);
                if (!checked && bulkVetIds.length === 0) {
                  setBulkVetIds(vets.data?.map((vet) => vet.id) ?? []);
                }
              }}
            />
            ทั้งหมด (All)
          </label>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {vets.data?.map((vet) => {
              const checked = bulkAllVets || bulkVetIds.includes(vet.id);
              return (
                <label
                  key={vet.id}
                  className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-700"
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={bulkAllVets}
                    onChange={(event) => toggleBulkVet(vet.id, event.target.checked)}
                  />
                  {vet.full_name}
                </label>
              );
            })}
          </div>
          {vets.data?.length === 0 ? (
            <p className="text-sm text-rose-600">ยังไม่มีสัตวแพทย์ที่ใช้งานอยู่</p>
          ) : null}
        </div>

        <div className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-950/30 dark:text-amber-200">
          กะเดิมของสัตวแพทย์และวันที่เลือกจะถูกแทนที่ทั้งหมด ระบบจะให้ยืนยันอีกครั้งก่อนสร้าง
        </div>

        <ErrorText error={bulkPreviewMutation.error} />
        <button
          type="submit"
          className="btn-primary"
          disabled={
            bulkPreviewMutation.isPending ||
            bulkInvalidRange ||
            bulkSelectedCount === 0 ||
            (vets.data?.length ?? 0) === 0
          }
        >
          {bulkPreviewMutation.isPending ? "กำลังตรวจสอบ..." : "สร้างกะแบบพิเศษ"}
        </button>
        {bulkInvalidRange ? (
          <p className="text-sm text-rose-600">วันที่สิ้นสุดต้องไม่น้อยกว่าวันที่เริ่มต้น</p>
        ) : null}
      </form>

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

      {bulkDialogOpen && bulkPreview ? (
        <div
          className="fixed inset-0 z-50 grid place-items-center bg-slate-950/50 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="bulk-shift-confirm-title"
        >
          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-5 shadow-xl dark:bg-slate-900">
            <h2 id="bulk-shift-confirm-title" className="text-lg font-bold">
              ยืนยันสร้างกะแบบพิเศษ
            </h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {bulkPreview.day_count} วัน · {bulkPreview.vet_count} สัตวแพทย์ ·{" "}
              {bulkPreview.shifts_to_create} กะ
            </p>

            <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-slate-500">ช่วงวันที่</dt>
                <dd className="font-medium">
                  {formatDate(bulkPreview.start_date)} – {formatDate(bulkPreview.end_date)}
                </dd>
              </div>
              <div>
                <dt className="text-slate-500">เวลา</dt>
                <dd className="font-medium">
                  {bulkStart}–{bulkEnd} น.
                </dd>
              </div>
            </dl>

            {bulkPreview.existing_shifts.length > 0 ? (
              <div className="mt-4 rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-950/30 dark:text-amber-200">
                พบกะเดิม {bulkPreview.existing_shifts.length} รายการในช่วงนี้
                ระบบจะแทนที่กะเดิมของวันนั้นทั้งหมด
              </div>
            ) : null}

            {bulkBlocked ? (
              <div className="mt-3 rounded-xl bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:bg-rose-950/30 dark:text-rose-200">
                มีกะเดิมที่มีนัดหมายอยู่ {bulkPreview.blocked_shifts.length} รายการ
                จึงยังแทนที่ไม่ได้ กรุณาจัดการนัดหมายก่อน
              </div>
            ) : null}

            {bulkPreview.existing_shifts.length > 0 ? (
              <div className="mt-3 max-h-56 space-y-2 overflow-y-auto">
                {bulkPreview.existing_shifts.map((shift) => (
                  <div
                    key={shift.shift_id}
                    className={`flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2 text-sm ${
                      shift.appointment_count > 0
                        ? "border-rose-200 bg-rose-50/40 dark:border-rose-900 dark:bg-rose-950/20"
                        : "border-slate-200 dark:border-slate-700"
                    }`}
                  >
                    <span className="font-medium">
                      {formatDate(shift.shift_date)} · {shift.vet_name}
                    </span>
                    <span className="text-slate-500">
                      {shift.start_time}–{shift.end_time} น.
                      {shift.appointment_count > 0
                        ? ` · มีนัด ${shift.appointment_count} รายการ`
                        : ""}
                    </span>
                  </div>
                ))}
              </div>
            ) : null}

            <ErrorText error={bulkCreate.error} />
            <div className="mt-4 flex flex-wrap justify-end gap-2">
              <button
                type="button"
                className="btn-secondary"
                disabled={bulkCreate.isPending}
                onClick={closeBulkDialog}
              >
                ยกเลิก
              </button>
              <button
                type="button"
                className="btn-primary"
                disabled={bulkCreate.isPending || bulkBlocked}
                onClick={() => bulkCreate.mutate(bulkPayload())}
              >
                {bulkCreate.isPending ? "กำลังสร้าง..." : "ยืนยันสร้างกะ"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
