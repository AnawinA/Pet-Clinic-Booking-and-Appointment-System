import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { endpoints } from "../../api/endpoints";
import { PetAvatar } from "../../components/PetAvatar";
import { EmptyState, ErrorText, PageHeader, Spinner, StatusBadge } from "../../components/ui";
import { formatDateTime } from "../../lib/format";

export default function AppointmentDetailPage() {
  const { id } = useParams<{ id: string }>();

  const appointment = useQuery({
    queryKey: ["appointment", id],
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

  const position = useQuery({
    queryKey: ["queue-position", id],
    queryFn: () => endpoints.appointments.queuePosition(id!),
    enabled: Boolean(id),
    refetchInterval: 3000,
    retry: false,
  });

  return (
    <div>
      <PageHeader
        title="รายละเอียดนัดหมาย"
        actions={
          <Link to="/owner/appointments" className="btn-secondary">
            กลับ
          </Link>
        }
      />

      <ErrorText error={appointment.error} />
      {appointment.isLoading ? <Spinner /> : null}

      {appointment.data ? (
        <section className="card mb-5">
          <div className="flex flex-wrap items-center gap-3">
            <PetAvatar
              petId={appointment.data.pet_id}
              name={appointment.data.pet_name ?? "สัตว์เลี้ยง"}
              size="md"
            />
            <h2 className="text-xl font-semibold">{appointment.data.pet_name}</h2>
            <StatusBadge status={appointment.data.status} />
          </div>
          <p className="mt-2 text-sm text-slate-600">
            {formatDateTime(appointment.data.slot_start)} น. · {appointment.data.vet_name}
          </p>
          <p className="mt-2 text-sm text-slate-500">อาการ: {appointment.data.symptoms}</p>
          <div className="mt-4 rounded-lg bg-slate-50 p-3 text-sm">
            {position.data ? (
              position.data.estimated_start ? (
                <>
                  <p className="font-medium text-slate-700">
                    คิวที่ {position.data.ahead_count + 1}
                  </p>
                  <p className="text-slate-500">
                    เวลาที่คาดว่าจะเริ่ม: {formatDateTime(position.data.estimated_start)} น.
                  </p>
                </>
              ) : (
                <p className="text-slate-500">นัดหมายนี้สิ้นสุดแล้ว</p>
              )
            ) : (
              <p className="text-slate-500">ยังไม่มีข้อมูลคิว</p>
            )}
          </div>
        </section>
      ) : null}

      <h2 className="mb-2 font-semibold">คำแนะนำการรักษา</h2>
      <ErrorText error={notes.error} />
      {notes.isLoading ? <Spinner /> : null}
      {notes.data && notes.data.length === 0 ? (
        <EmptyState title="ยังไม่มีบันทึกการรักษา" hint="สัตวแพทย์จะบันทึกหลังการตรวจ" />
      ) : null}
      <div className="space-y-2">
        {notes.data?.map((note) => (
          <article key={note.id} className="card">
            <div className="flex items-center justify-between text-xs text-slate-500">
              <span>
                เวอร์ชัน {note.version} · {note.author_name}
              </span>
              <span>{formatDateTime(note.created_at)}</span>
            </div>
            <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{note.content}</p>
          </article>
        ))}
      </div>
    </div>
  );
}
