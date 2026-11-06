import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { endpoints } from "../api/endpoints";
import { pushToast } from "../components/Toast";
import { EmptyState, ErrorText, PageHeader, Spinner } from "../components/ui";
import { formatDateTime } from "../lib/format";

export default function NotificationsPage() {
  const queryClient = useQueryClient();
  const notifications = useQuery({
    queryKey: ["notifications"],
    queryFn: () => endpoints.notifications.list({ limit: 100 }),
    refetchInterval: 5000,
  });

  const markRead = useMutation({
    mutationFn: (id: string) => endpoints.notifications.markRead(id),
    onSuccess: () => {
      pushToast("success", "ทำเครื่องหมายว่าอ่านแล้ว");
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  return (
    <div>
      <PageHeader
        title="การแจ้งเตือน"
        subtitle="อัปเดตอัตโนมัติทุก 5 วินาที"
        actions={
          <button
            type="button"
            className="btn-secondary"
            onClick={() => void queryClient.invalidateQueries({ queryKey: ["notifications"] })}
          >
            รีเฟรช
          </button>
        }
      />

      <ErrorText error={notifications.error} />
      {notifications.isLoading ? <Spinner /> : null}

      {notifications.data && notifications.data.length === 0 ? (
        <EmptyState title="ยังไม่มีการแจ้งเตือน" hint="เมื่อมีการจองหรือเปลี่ยนสถานะจะแสดงที่นี่" />
      ) : null}

      <div className="space-y-2">
        {notifications.data?.map((item) => (
          <article
            key={item.id}
            className={`card flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between ${
              item.is_read ? "opacity-70" : ""
            }`}
          >
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-semibold">{item.title}</h2>
                {!item.is_read ? (
                  <span className="rounded-full bg-brand-100 px-2 py-0.5 text-xs font-semibold text-brand-700">
                    ใหม่
                  </span>
                ) : null}
              </div>
              <p className="mt-1 text-sm text-slate-600">{item.message}</p>
              <p className="mt-1 text-xs text-slate-400">{formatDateTime(item.created_at)}</p>
            </div>
            {!item.is_read ? (
              <button
                type="button"
                className="btn-secondary shrink-0"
                onClick={() => markRead.mutate(item.id)}
                disabled={markRead.isPending}
              >
                อ่านแล้ว
              </button>
            ) : null}
          </article>
        ))}
      </div>
    </div>
  );
}
