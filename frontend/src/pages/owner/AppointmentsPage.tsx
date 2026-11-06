import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { endpoints } from "../../api/endpoints";
import type { Appointment } from "../../api/types";
import { PetAvatar } from "../../components/PetAvatar";
import { pushToast } from "../../components/Toast";
import {
  EmptyState,
  ErrorText,
  Modal,
  PageHeader,
  Spinner,
  StatusBadge,
} from "../../components/ui";
import { canOwnerCancel, formatDateTime } from "../../lib/format";

export default function AppointmentsPage() {
  const queryClient = useQueryClient();
  const appointments = useQuery({
    queryKey: ["appointments"],
    queryFn: endpoints.appointments.list,
    refetchInterval: 5000,
  });

  const [target, setTarget] = useState<Appointment | null>(null);
  const [reason, setReason] = useState("");

  const cancel = useMutation({
    mutationFn: (appointment: Appointment) => endpoints.appointments.cancel(appointment.id, reason),
    onSuccess: () => {
      pushToast("success", "ยกเลิกนัดหมายแล้ว");
      setTarget(null);
      setReason("");
      void queryClient.invalidateQueries({ queryKey: ["appointments"] });
    },
  });

  return (
    <div>
      <PageHeader
        title="นัดหมายของฉัน"
        subtitle="ข้อมูลอัปเดตอัตโนมัติทุก 5 วินาที"
        actions={
          <Link to="/owner/book" className="btn-primary">
            จองนัดใหม่
          </Link>
        }
      />

      <ErrorText error={appointments.error} />
      {appointments.isLoading ? <Spinner /> : null}
      {appointments.data && appointments.data.length === 0 ? (
        <EmptyState title="ยังไม่มีนัดหมาย" hint="เริ่มจองนัดให้สัตว์เลี้ยงของคุณได้เลย" />
      ) : null}

      <div className="space-y-3">
        {appointments.data?.map((appointment) => {
          const cancellable =
            appointment.status === "BOOKED" && canOwnerCancel(appointment.slot_start);
          return (
            <article key={appointment.id} className="card">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="flex items-start gap-3">
                  <PetAvatar
                    petId={appointment.pet_id}
                    name={appointment.pet_name ?? "สัตว์เลี้ยง"}
                    size="md"
                  />
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="text-lg font-semibold">{appointment.pet_name ?? "สัตว์เลี้ยง"}</h2>
                    <StatusBadge status={appointment.status} />
                  </div>
                  <p className="mt-1 text-sm text-slate-600">
                    {formatDateTime(appointment.slot_start)} น. · {appointment.vet_name}
                  </p>
                  <p className="mt-1 text-sm text-slate-500">อาการ: {appointment.symptoms}</p>
                    {appointment.cancel_reason ? (
                      <p className="mt-1 text-xs text-rose-600">
                        เหตุผลที่ยกเลิก: {appointment.cancel_reason}
                      </p>
                    ) : null}
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Link to={`/owner/appointments/${appointment.id}`} className="btn-secondary">
                    รายละเอียด
                  </Link>
                  {cancellable ? (
                    <button
                      type="button"
                      className="btn-danger"
                      onClick={() => {
                        setTarget(appointment);
                        setReason("");
                      }}
                    >
                      ยกเลิกนัด
                    </button>
                  ) : null}
                </div>
              </div>
              {appointment.status === "BOOKED" && !cancellable ? (
                <p className="mt-2 text-xs text-amber-700">
                  ไม่สามารถยกเลิกได้เมื่อเหลือเวลาน้อยกว่า 2 ชั่วโมงก่อนนัด กรุณาติดต่อคลินิก
                </p>
              ) : null}
            </article>
          );
        })}
      </div>

      <Modal open={Boolean(target)} title="ยืนยันการยกเลิกนัด" onClose={() => setTarget(null)}>
        <p className="text-sm text-slate-600">
          {target ? `${target.pet_name} · ${formatDateTime(target.slot_start)} น.` : ""}
        </p>
        <label className="mt-3 block">
          <span className="label">เหตุผล (ไม่บังคับ)</span>
          <textarea
            className="input min-h-20"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </label>
        <ErrorText error={cancel.error} />
        <div className="mt-4 flex justify-end gap-2">
          <button type="button" className="btn-secondary" onClick={() => setTarget(null)}>
            ไม่ยกเลิก
          </button>
          <button
            type="button"
            className="btn-danger"
            disabled={cancel.isPending}
            onClick={() => target && cancel.mutate(target)}
          >
            {cancel.isPending ? "กำลังยกเลิก..." : "ยืนยันยกเลิก"}
          </button>
        </div>
      </Modal>
    </div>
  );
}
