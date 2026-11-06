import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { fieldErrors } from "../../api/client";
import { endpoints } from "../../api/endpoints";
import { PetAvatar } from "../../components/PetAvatar";
import { pushToast } from "../../components/Toast";
import { EmptyState, ErrorText, Field, PageHeader, Spinner, StatusBadge } from "../../components/ui";
import { bangkokInputToIso, formatDateTime } from "../../lib/format";

export default function CaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [content, setContent] = useState("");
  const [proposed, setProposed] = useState("");
  const [reason, setReason] = useState("");

  const appointment = useQuery({
    queryKey: ["case", id],
    queryFn: () => endpoints.appointments.detail(id!),
    enabled: Boolean(id),
    refetchInterval: 5000,
  });

  const notes = useQuery({
    queryKey: ["notes", id],
    queryFn: () => endpoints.appointments.notes(id!),
    enabled: Boolean(id),
    refetchInterval: 5000,
  });

  const history = useQuery({
    queryKey: ["pet-history", appointment.data?.pet_id],
    queryFn: () => endpoints.pets.history(appointment.data!.pet_id),
    enabled: Boolean(appointment.data?.pet_id),
  });

  const addNote = useMutation({
    mutationFn: () => endpoints.appointments.addNote(id!, content.trim()),
    onSuccess: () => {
      pushToast("success", "บันทึกการรักษาแล้ว");
      setContent("");
      void queryClient.invalidateQueries({ queryKey: ["notes", id] });
      void queryClient.invalidateQueries({ queryKey: ["pet-history"] });
    },
  });

  const requestReschedule = useMutation({
    mutationFn: () =>
      endpoints.appointments.requestReschedule(id!, bangkokInputToIso(proposed), reason.trim()),
    onSuccess: () => {
      pushToast("success", "ส่งคำขอปรับเวลาแล้ว");
      setProposed("");
      setReason("");
    },
  });

  const noteErrors = fieldErrors(addNote.error);
  const requestErrors = fieldErrors(requestReschedule.error);

  const submitNote = (event: FormEvent) => {
    event.preventDefault();
    if (!content.trim()) {
      pushToast("error", "กรุณากรอกบันทึกการรักษา");
      return;
    }
    addNote.mutate();
  };

  const submitRequest = (event: FormEvent) => {
    event.preventDefault();
    if (!proposed || !reason.trim()) {
      pushToast("error", "กรุณาระบุเวลาใหม่และเหตุผล");
      return;
    }
    requestReschedule.mutate();
  };

  return (
    <div>
      <PageHeader
        title="รายละเอียดเคส"
        actions={
          <Link to="/vet/schedule" className="btn-secondary">
            กลับตารางงาน
          </Link>
        }
      />

      <ErrorText error={appointment.error} />
      {appointment.isLoading ? <Spinner /> : null}

      {appointment.data ? (
        <section className="card mb-5">
          <div className="flex flex-wrap items-center gap-2">
            <PetAvatar
              petId={appointment.data.pet_id}
              name={appointment.data.pet_name ?? "สัตว์เลี้ยง"}
              size="md"
            />
            <h2 className="text-xl font-semibold">{appointment.data.pet_name}</h2>
            <StatusBadge status={appointment.data.status} />
          </div>
          <p className="mt-1 text-sm text-slate-600">
            {formatDateTime(appointment.data.slot_start)} น. · เจ้าของ {appointment.data.owner_name}
          </p>
          <p className="mt-2 text-sm text-slate-600">อาการ: {appointment.data.symptoms}</p>
        </section>
      ) : null}

      <div className="grid gap-5 lg:grid-cols-[1.2fr_1fr]">
        <section>
          <h2 className="mb-2 font-semibold">บันทึกการรักษา (มีเวอร์ชัน)</h2>
          <form className="card mb-4" onSubmit={submitNote}>
            <Field label="บันทึกใหม่" error={noteErrors.content}>
              <textarea
                className="input min-h-24"
                value={content}
                onChange={(event) => setContent(event.target.value)}
                placeholder="การวินิจฉัย การรักษา ยาที่จ่าย และคำแนะนำ"
              />
            </Field>
            <ErrorText error={addNote.error} />
            <button type="submit" className="btn-primary mt-3" disabled={addNote.isPending}>
              {addNote.isPending ? "กำลังบันทึก..." : "บันทึกเวอร์ชันใหม่"}
            </button>
          </form>

          <ErrorText error={notes.error} />
          {notes.isLoading ? <Spinner /> : null}
          {notes.data && notes.data.length === 0 ? (
            <EmptyState title="ยังไม่มีบันทึก" hint="บันทึกครั้งแรกจะเป็นเวอร์ชัน 1" />
          ) : null}
          <div className="space-y-2">
            {notes.data?.map((note) => (
              <article key={note.id} className="card">
                <div className="flex justify-between text-xs text-slate-500">
                  <span>เวอร์ชัน {note.version}</span>
                  <span>{formatDateTime(note.created_at)}</span>
                </div>
                <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{note.content}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="space-y-5">
          <div>
            <h2 className="mb-2 font-semibold">ขอปรับเวลา</h2>
            <form className="card space-y-3" onSubmit={submitRequest}>
              <Field label="เวลาใหม่ (เวลาไทย)" error={requestErrors.proposed_slot_start}>
                <input
                  className="input"
                  type="datetime-local"
                  value={proposed}
                  onChange={(event) => setProposed(event.target.value)}
                />
              </Field>
              <Field label="เหตุผล" error={requestErrors.reason}>
                <textarea
                  className="input min-h-20"
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                />
              </Field>
              <ErrorText error={requestReschedule.error} />
              <button type="submit" className="btn-secondary w-full" disabled={requestReschedule.isPending}>
                {requestReschedule.isPending ? "กำลังส่ง..." : "ส่งคำขอถึงเจ้าหน้าที่"}
              </button>
            </form>
          </div>

          <div>
            <h2 className="mb-2 font-semibold">ประวัติการรักษาของสัตว์ตัวนี้</h2>
            <ErrorText error={history.error} />
            {history.isLoading ? <Spinner /> : null}
            {history.data && history.data.length === 0 ? (
              <EmptyState title="ไม่มีประวัติ" />
            ) : null}
            <div className="space-y-2">
              {history.data?.map((entry) => (
                <article key={entry.appointment.id} className="card">
                  <div className="flex items-center justify-between text-sm">
                    <span>{formatDateTime(entry.appointment.slot_start)}</span>
                    <StatusBadge status={entry.appointment.status} />
                  </div>
                  <p className="mt-1 text-xs text-slate-500">
                    {entry.appointment.vet_name} · {entry.treatment_notes.length} บันทึก
                  </p>
                  {entry.treatment_notes.length > 0 ? (
                    <p className="mt-2 line-clamp-3 text-sm text-slate-600">
                      {entry.treatment_notes[entry.treatment_notes.length - 1].content}
                    </p>
                  ) : null}
                </article>
              ))}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
