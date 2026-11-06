import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { endpoints } from "../../api/endpoints";
import { pushToast } from "../../components/Toast";
import { EmptyState, ErrorText, PageHeader, Spinner } from "../../components/ui";
import { formatDateTime } from "../../lib/format";

export default function RescheduleApprovalsPage() {
  const queryClient = useQueryClient();
  const [notes, setNotes] = useState<Record<string, string>>({});

  const requests = useQuery({
    queryKey: ["reschedule-requests", "PENDING"],
    queryFn: () => endpoints.rescheduleRequests.list("PENDING"),
    refetchInterval: 5000,
  });

  const review = useMutation({
    mutationFn: (args: { id: string; approve: boolean }) =>
      args.approve
        ? endpoints.rescheduleRequests.approve(args.id, notes[args.id] ?? "")
        : endpoints.rescheduleRequests.reject(args.id, notes[args.id] ?? ""),
    onSuccess: () => {
      pushToast("success", "บันทึกผลการตรวจสอบแล้ว");
      void queryClient.invalidateQueries({ queryKey: ["reschedule-requests"] });
    },
  });

  return (
    <div>
      <PageHeader
        title="คำขอปรับเวลา"
        subtitle="อนุมัติแล้วระบบจะเลื่อนนัดให้ทันที หากสล็อตชนจะแจ้งข้อผิดพลาด"
        actions={
          <button
            type="button"
            className="btn-secondary"
            onClick={() => void queryClient.invalidateQueries({ queryKey: ["reschedule-requests"] })}
          >
            รีเฟรช
          </button>
        }
      />

      <ErrorText error={requests.error} />
      {requests.isLoading ? <Spinner /> : null}
      {requests.data && requests.data.length === 0 ? (
        <EmptyState title="ไม่มีคำขอรอตรวจสอบ" />
      ) : null}

      <div className="space-y-3">
        {requests.data?.map((request) => (
          <article key={request.id} className="card space-y-3">
            <div>
              <p className="font-semibold">
                ผู้ขอ: {request.requester_name ?? "-"}{" "}
                <span className="text-sm font-normal text-slate-500">
                  · นัด {formatDateTime(request.proposed_slot_start)} น.
                </span>
              </p>
              <p className="mt-1 text-sm text-slate-600">เหตุผล: {request.reason}</p>
              <p className="mt-1 text-xs text-slate-400">
                ส่งเมื่อ {formatDateTime(request.created_at)} · นัดหมาย {request.appointment_id}
              </p>
            </div>
            <input
              className="input"
              placeholder="บันทึกผลการพิจารณา (ไม่บังคับ)"
              value={notes[request.id] ?? ""}
              onChange={(event) =>
                setNotes((current) => ({ ...current, [request.id]: event.target.value }))
              }
            />
            <ErrorText error={review.error} />
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="btn-primary"
                disabled={review.isPending}
                onClick={() => review.mutate({ id: request.id, approve: true })}
              >
                อนุมัติ
              </button>
              <button
                type="button"
                className="btn-danger"
                disabled={review.isPending}
                onClick={() => review.mutate({ id: request.id, approve: false })}
              >
                ปฏิเสธ
              </button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
