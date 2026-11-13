import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { endpoints } from "../../api/endpoints";
import type { AppointmentStatus, ScheduleEntry } from "../../api/types";
import { PetAvatar } from "../../components/PetAvatar";
import { TimeInput } from "../../components/TimeInput";
import { pushToast } from "../../components/Toast";
import {
  EmptyState,
  ErrorText,
  Field,
  Modal,
  PageHeader,
  Spinner,
  StatusBadge,
} from "../../components/ui";
import { bangkokInputToIso, bangkokToday, formatDateTime, formatTime } from "../../lib/format";

const NEXT: Record<AppointmentStatus, AppointmentStatus[]> = {
  BOOKED: ["CHECKED_IN", "NO_SHOW", "CANCELLED"],
  CHECKED_IN: ["IN_TREATMENT", "NO_SHOW"],
  IN_TREATMENT: ["COMPLETED"],
  COMPLETED: [],
  NO_SHOW: [],
  CANCELLED: [],
};

const ACTION_LABELS: Record<AppointmentStatus, string> = {
  BOOKED: "จอง",
  CHECKED_IN: "เช็คอิน",
  IN_TREATMENT: "เริ่มรักษา",
  COMPLETED: "เสร็จสิ้น",
  NO_SHOW: "ไม่มา",
  CANCELLED: "ยกเลิก",
};

export default function BoardPage() {
  const queryClient = useQueryClient();
  const vets = useQuery({ queryKey: ["vets"], queryFn: endpoints.vets.list });
  const [date, setDate] = useState(bangkokToday(0));
  const [vetId, setVetId] = useState("");
  const [swapIds, setSwapIds] = useState<string[]>([]);
  const [rescheduleTarget, setRescheduleTarget] = useState<ScheduleEntry | null>(null);
  const [newSlotDate, setNewSlotDate] = useState("");
  const [newSlotTime, setNewSlotTime] = useState("09:00");
  const [transferTarget, setTransferTarget] = useState<ScheduleEntry | null>(null);
  const newSlot = newSlotDate ? `${newSlotDate}T${newSlotTime}` : "";
  const [transferVet, setTransferVet] = useState("");

  useEffect(() => {
    if (!vetId && vets.data && vets.data.length > 0) setVetId(vets.data[0].id);
  }, [vetId, vets.data]);

  const board = useQuery({
    queryKey: ["board", date, vetId],
    queryFn: () => endpoints.schedule.list(date, vetId),
    enabled: Boolean(vetId),
    refetchInterval: 5000,
  });

  const invalidateBoard = () => {
    void queryClient.invalidateQueries({ queryKey: ["board"] });
    void queryClient.invalidateQueries({ queryKey: ["notifications"] });
  };

  const statusMutation = useMutation({
    mutationFn: (args: { entry: ScheduleEntry; status: AppointmentStatus }) =>
      endpoints.appointments.updateStatus(args.entry.appointment_id, args.status, args.entry.version),
    onSuccess: () => {
      pushToast("success", "อัปเดตสถานะแล้ว");
      invalidateBoard();
    },
  });

  const rescheduleMutation = useMutation({
    mutationFn: () => {
      if (!rescheduleTarget) throw new Error("ไม่พบนัดหมาย");
      return endpoints.appointments.reschedule(
        rescheduleTarget.appointment_id,
        bangkokInputToIso(newSlot),
        rescheduleTarget.version,
      );
    },
    onSuccess: () => {
      pushToast("success", "เลื่อนนัดหมายแล้ว");
      setRescheduleTarget(null);
      setNewSlotDate("");
      setNewSlotTime("09:00");
      invalidateBoard();
    },
  });

  const transferMutation = useMutation({
    mutationFn: () => {
      if (!transferTarget) throw new Error("ไม่พบนัดหมาย");
      return endpoints.appointments.transfer(
        transferTarget.appointment_id,
        transferVet,
        transferTarget.version,
      );
    },
    onSuccess: () => {
      pushToast("success", "โอนเคสแล้ว");
      setTransferTarget(null);
      setTransferVet("");
      invalidateBoard();
    },
  });

  const selectedForSwap = useMemo(() => {
    const items = board.data?.items ?? [];
    return swapIds
      .map((id) => items.find((item) => item.appointment_id === id))
      .filter((item): item is ScheduleEntry => Boolean(item));
  }, [board.data, swapIds]);

  const canSwap =
    selectedForSwap.length === 2 && selectedForSwap.every((item) => item.status === "BOOKED");

  const swapMutation = useMutation({
    mutationFn: () =>
      endpoints.appointments.swap(
        selectedForSwap[0].appointment_id,
        selectedForSwap[1].appointment_id,
        selectedForSwap[0].version,
        selectedForSwap[1].version,
      ),
    onSuccess: () => {
      pushToast("success", "สลับคิวแล้ว");
      setSwapIds([]);
      invalidateBoard();
    },
  });

  const toggleSwap = (id: string) => {
    setSwapIds((current) => {
      if (current.includes(id)) return current.filter((item) => item !== id);
      return [...current, id].slice(-2);
    });
  };

  return (
    <div>
      <PageHeader title="กระดานนัดหมาย" subtitle="กรองตามสัตวแพทย์และจัดการสถานะเคส" />

      <div className="card mb-5 grid gap-3 sm:grid-cols-3">
        <Field label="วันที่">
          <input
            className="input"
            type="date"
            value={date}
            onChange={(event) => {
              setDate(event.target.value);
              setSwapIds([]);
            }}
          />
        </Field>
        <Field label="สัตวแพทย์">
          <select
            className="input"
            value={vetId}
            onChange={(event) => {
              setVetId(event.target.value);
              setSwapIds([]);
            }}
          >
            {vets.data?.map((vet) => (
              <option key={vet.id} value={vet.id}>
                {vet.full_name}
              </option>
            ))}
          </select>
        </Field>
        <div className="flex items-end">
          <button
            type="button"
            className="btn-secondary w-full"
            disabled={!canSwap || swapMutation.isPending}
            onClick={() => swapMutation.mutate()}
          >
            สลับคิวที่เลือก ({selectedForSwap.length}/2)
          </button>
        </div>
      </div>

      <ErrorText error={board.error} />
      {board.isLoading ? <Spinner /> : null}
      {board.data && board.data.items.length === 0 ? (
        <EmptyState title="ไม่มีนัดในวันนี้" hint="เปลี่ยนวันหรือสัตวแพทย์" />
      ) : null}

      <div className="space-y-3">
        {board.data?.items.map((entry) => (
          <article key={entry.appointment_id} className="card">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div className="flex gap-3">
                <input
                  type="checkbox"
                  aria-label={`เลือก ${entry.pet_name} เพื่อสลับคิว`}
                  className="mt-1 h-4 w-4"
                  checked={swapIds.includes(entry.appointment_id)}
                  onChange={() => toggleSwap(entry.appointment_id)}
                />
                <PetAvatar petId={entry.pet_id} name={entry.pet_name} size="md" />
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="font-semibold">{entry.pet_name}</h2>
                    <StatusBadge status={entry.status} />
                    <span className="text-xs text-slate-400">เจ้าของ {entry.owner_name}</span>
                  </div>
                  <p className="text-sm text-slate-500">
                    {formatTime(entry.slot_start)}–{formatTime(entry.slot_end)} น.
                    {entry.estimated_start
                      ? ` · คาดว่าเริ่ม ${formatDateTime(entry.estimated_start)} น.`
                      : ""}
                  </p>
                  <p className="mt-1 text-sm text-slate-600">อาการ: {entry.symptoms}</p>
                </div>
              </div>

              <div className="flex flex-wrap gap-1.5">
                {NEXT[entry.status]
                  .filter((next) => next !== "NO_SHOW" || Date.now() >= Date.parse(entry.slot_start))
                  .map((next) => (
                    <button
                      key={next}
                      type="button"
                      className={
                        next === "CANCELLED" || next === "NO_SHOW"
                          ? "btn-secondary"
                          : "btn-primary"
                      }
                      disabled={statusMutation.isPending}
                      onClick={() => statusMutation.mutate({ entry, status: next })}
                    >
                      {ACTION_LABELS[next]}
                    </button>
                  ))}
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => {
                    setRescheduleTarget(entry);
                    setNewSlotDate("");
                    setNewSlotTime("09:00");
                  }}
                >
                  เลื่อนนัด
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => {
                    setTransferTarget(entry);
                    setTransferVet("");
                  }}
                >
                  โอนเคส
                </button>
              </div>
            </div>
          </article>
        ))}
      </div>

      <Modal
        open={Boolean(rescheduleTarget)}
        title="เลื่อนนัดหมาย"
        onClose={() => setRescheduleTarget(null)}
      >
        <p className="text-sm text-slate-600">
          {rescheduleTarget ? `${rescheduleTarget.pet_name} · ${formatDateTime(rescheduleTarget.slot_start)} น.` : ""}
        </p>
        <div className="mt-2 grid gap-3 sm:grid-cols-[1.15fr_1fr]">
          <Field label="วันที่ใหม่ (เวลาไทย)">
            <input
              className="input mt-2"
              type="date"
              value={newSlotDate}
              onChange={(event) => setNewSlotDate(event.target.value)}
            />
          </Field>
          <Field label="เวลาใหม่ (เวลาไทย)">
            <TimeInput
              className="input mt-2"
              value={newSlotTime}
              min="09:00"
              max="16:30"
              onChange={setNewSlotTime}
            />
          </Field>
        </div>
        <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
          เลือกเวลาเป็นรอบละ 30 นาที ระหว่าง 09:00–16:30 น.
        </p>
        <ErrorText error={rescheduleMutation.error} />
        <div className="mt-4 flex justify-end gap-2">
          <button type="button" className="btn-secondary" onClick={() => setRescheduleTarget(null)}>
            ปิด
          </button>
          <button
            type="button"
            className="btn-primary"
            disabled={!newSlot || rescheduleMutation.isPending}
            onClick={() => rescheduleMutation.mutate()}
          >
            ยืนยันเลื่อนนัด
          </button>
        </div>
      </Modal>

      <Modal open={Boolean(transferTarget)} title="โอนเคสให้สัตวแพทย์ท่านอื่น" onClose={() => setTransferTarget(null)}>
        <p className="text-sm text-slate-600">
          {transferTarget ? `${transferTarget.pet_name} · ${formatDateTime(transferTarget.slot_start)} น.` : ""}
        </p>
        <Field label="สัตวแพทย์ปลายทาง">
          <select
            className="input mt-2"
            value={transferVet}
            onChange={(event) => setTransferVet(event.target.value)}
          >
            <option value="">เลือกสัตวแพทย์</option>
            {vets.data
              ?.filter((vet) => vet.id !== transferTarget?.vet_id)
              .map((vet) => (
                <option key={vet.id} value={vet.id}>
                  {vet.full_name}
                </option>
              ))}
          </select>
        </Field>
        <ErrorText error={transferMutation.error} />
        <div className="mt-4 flex justify-end gap-2">
          <button type="button" className="btn-secondary" onClick={() => setTransferTarget(null)}>
            ปิด
          </button>
          <button
            type="button"
            className="btn-primary"
            disabled={!transferVet || transferMutation.isPending}
            onClick={() => transferMutation.mutate()}
          >
            ยืนยันโอนเคส
          </button>
        </div>
      </Modal>
    </div>
  );
}
