import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { endpoints } from "../../api/endpoints";
import { EmptyState, ErrorText, Field, PageHeader, Spinner } from "../../components/ui";
import { formatDateTime } from "../../lib/format";

export default function AuditPage() {
  const [entityId, setEntityId] = useState("");
  const [action, setAction] = useState("");

  const logs = useQuery({
    queryKey: ["audit", entityId, action],
    queryFn: () =>
      endpoints.audit.list({
        entityId: entityId.trim() || undefined,
        action: action.trim() || undefined,
        limit: 200,
      }),
    refetchInterval: 5000,
  });

  return (
    <div>
      <PageHeader title="Audit Log" subtitle="บันทึกการเปลี่ยนแปลงแบบ append-only" />

      <div className="card mb-5 grid gap-3 sm:grid-cols-2">
        <Field label="Entity ID">
          <input
            className="input"
            value={entityId}
            onChange={(event) => setEntityId(event.target.value)}
            placeholder="UUID ของนัดหมาย/สัตว์เลี้ยง"
          />
        </Field>
        <Field label="Action">
          <input
            className="input"
            value={action}
            onChange={(event) => setAction(event.target.value)}
            placeholder="STATUS_CHANGE, RESCHEDULE, TRANSFER, SWAP..."
          />
        </Field>
      </div>

      <ErrorText error={logs.error} />
      {logs.isLoading ? <Spinner /> : null}
      {logs.data && logs.data.length === 0 ? <EmptyState title="ไม่พบรายการ" /> : null}

      <div className="space-y-2">
        {logs.data?.map((log) => (
          <article key={log.id} className="card">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-semibold">{log.action}</span>
                <span className="text-sm text-slate-600">
                  {log.entity_type} · {log.entity_id}
                </span>
              </div>
              <span className="text-xs text-slate-400">{formatDateTime(log.created_at)}</span>
            </div>
            <p className="mt-2 text-xs text-slate-500">
              ผู้ทำ: {log.actor_role ?? "SYSTEM"} {log.actor_id ?? ""} · request {log.request_id ?? "-"}
            </p>
            <details className="mt-2 text-xs">
              <summary className="cursor-pointer text-slate-500">ดูรายละเอียด before/after</summary>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                <pre className="overflow-x-auto rounded bg-slate-50 p-2">
                  {JSON.stringify(log.before, null, 2) ?? "null"}
                </pre>
                <pre className="overflow-x-auto rounded bg-slate-50 p-2">
                  {JSON.stringify(log.after, null, 2) ?? "null"}
                </pre>
              </div>
            </details>
          </article>
        ))}
      </div>
    </div>
  );
}
