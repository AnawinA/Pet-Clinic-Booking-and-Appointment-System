import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { fieldErrors } from "../../api/client";
import { endpoints } from "../../api/endpoints";
import type {
  StaffAppointmentResolution,
  StaffUpcomingAppointment,
  User,
} from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { pushToast } from "../../components/Toast";
import { EmptyState, ErrorText, Field, PageHeader, Spinner } from "../../components/ui";
import { formatDateTime } from "../../lib/format";

const ROLE_LABELS = {
  VET: "สัตวแพทย์",
  STAFF: "เจ้าหน้าที่",
} as const;

type DeleteVariables = {
  account: User;
  appointments: StaffAppointmentResolution[];
};

export default function AccountsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    email: "",
    password: "",
    full_name: "",
    phone: "",
    role: "VET" as "VET" | "STAFF",
  });
  const [deleteTarget, setDeleteTarget] = useState<User | null>(null);
  const [affected, setAffected] = useState<StaffUpcomingAppointment[]>([]);
  const [choices, setChoices] = useState<Record<string, string>>({});
  const [preparingId, setPreparingId] = useState<string | null>(null);

  const accounts = useQuery({
    queryKey: ["staff-accounts"],
    queryFn: endpoints.auth.listStaff,
  });

  const vets = useQuery({
    queryKey: ["vets"],
    queryFn: endpoints.vets.list,
  });

  const create = useMutation({
    mutationFn: () =>
      endpoints.auth.createStaff({
        email: form.email.trim(),
        password: form.password,
        full_name: form.full_name.trim(),
        phone: form.phone.trim() || null,
        role: form.role,
      }),
    onSuccess: (created) => {
      pushToast("success", `สร้างบัญชี ${created.role} สำเร็จ: ${created.email}`);
      setForm({ email: "", password: "", full_name: "", phone: "", role: "VET" });
      void queryClient.invalidateQueries({ queryKey: ["staff-accounts"] });
    },
  });

  const remove = useMutation({
    mutationFn: ({ account, appointments }: DeleteVariables) =>
      endpoints.auth.deleteStaff(account.id, appointments),
    onSuccess: (result, { account }) => {
      pushToast("success", result.message || `ลบบัญชี ${account.email} แล้ว`);
      setDeleteTarget(null);
      setAffected([]);
      setChoices({});
      void queryClient.invalidateQueries({ queryKey: ["staff-accounts"] });
      void queryClient.invalidateQueries({ queryKey: ["vets"] });
      void queryClient.invalidateQueries({ queryKey: ["availability"] });
      void queryClient.invalidateQueries({ queryKey: ["board"] });
      void queryClient.invalidateQueries({ queryKey: ["shifts"] });
    },
  });

  const errors = fieldErrors(create.error);
  const replacementVets =
    vets.data?.filter((vet) => vet.id !== deleteTarget?.id) ?? [];
  const allChosen =
    affected.length > 0 &&
    affected.every((appointment) => Boolean(choices[appointment.appointment_id]));

  const openDelete = async (account: User) => {
    if (account.role === "STAFF") {
      if (
        window.confirm(
          `ลบบัญชี ${account.full_name} (${account.email}) ใช่หรือไม่?\nบัญชีนี้จะเข้าสู่ระบบไม่ได้`,
        )
      ) {
        remove.mutate({ account, appointments: [] });
      }
      return;
    }

    setPreparingId(account.id);
    try {
      const upcoming = await endpoints.auth.upcomingAppointments(account.id);
      if (upcoming.length === 0) {
        if (
          window.confirm(
            `ลบบัญชี ${account.full_name} (${account.email}) ใช่หรือไม่?\nไม่มีนัดที่ต้องจัดการ`,
          )
        ) {
          remove.mutate({ account, appointments: [] });
        }
        return;
      }
      setDeleteTarget(account);
      setAffected(upcoming);
      setChoices({});
    } catch (error) {
      pushToast(
        "error",
        error instanceof Error ? error.message : "ไม่สามารถโหลดนัดหมายของสัตวแพทย์ได้",
      );
    } finally {
      setPreparingId(null);
    }
  };

  const confirmDeleteWithResolutions = () => {
    if (!deleteTarget || !allChosen) return;
    const appointments: StaffAppointmentResolution[] = affected.map((appointment) => {
      const value = choices[appointment.appointment_id];
      if (value === "CANCEL") {
        return { appointment_id: appointment.appointment_id, action: "CANCEL" };
      }
      return {
        appointment_id: appointment.appointment_id,
        action: "TRANSFER",
        replacement_vet_id: value.slice("TRANSFER:".length),
      };
    });
    remove.mutate({ account: deleteTarget, appointments });
  };

  return (
    <div>
      <PageHeader
        title="จัดการบัญชีสัตวแพทย์ / เจ้าหน้าที่"
        subtitle="สร้างและลบบัญชีทีมงาน VET/STAFF — เฉพาะเจ้าหน้าที่เท่านั้น"
      />

      <form
        className="card grid max-w-2xl gap-3 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault();
          create.mutate();
        }}
      >
        <Field label="ชื่อ-นามสกุล" error={errors.full_name}>
          <input
            className="input"
            required
            value={form.full_name}
            onChange={(event) => setForm({ ...form, full_name: event.target.value })}
          />
        </Field>
        <Field label="อีเมล" error={errors.email}>
          <input
            className="input"
            type="email"
            required
            value={form.email}
            onChange={(event) => setForm({ ...form, email: event.target.value })}
          />
        </Field>
        <Field label="เบอร์โทร" error={errors.phone}>
          <input
            className="input"
            value={form.phone}
            onChange={(event) => setForm({ ...form, phone: event.target.value })}
          />
        </Field>
        <Field label="บทบาท">
          <select
            className="input"
            value={form.role}
            onChange={(event) => setForm({ ...form, role: event.target.value as "VET" | "STAFF" })}
          >
            <option value="VET">VET (สัตวแพทย์)</option>
            <option value="STAFF">STAFF (เจ้าหน้าที่)</option>
          </select>
        </Field>
        <div className="sm:col-span-2">
          <Field label="รหัสผ่านชั่วคราว (อย่างน้อย 8 ตัวอักษร)" error={errors.password}>
            <input
              className="input"
              type="password"
              minLength={8}
              required
              value={form.password}
              onChange={(event) => setForm({ ...form, password: event.target.value })}
            />
          </Field>
        </div>
        <div className="sm:col-span-2">
          <ErrorText error={create.error} />
          <button type="submit" className="btn-primary mt-3" disabled={create.isPending}>
            {create.isPending ? "กำลังสร้างบัญชี..." : "สร้างบัญชี"}
          </button>
        </div>
      </form>

      <section className="card mt-6 max-w-2xl">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h2 className="text-lg font-bold">บัญชีทีมงาน</h2>
            <p className="mt-1 text-sm text-slate-500">
              ไม่สามารถลบบัญชีของตัวเองได้ และระบบต้องมีบัญชี STAFF อย่างน้อย 1 บัญชี
            </p>
          </div>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
            {accounts.data?.length ?? 0} บัญชี
          </span>
        </div>

        <ErrorText error={accounts.error} />
        <ErrorText error={remove.error} />
        {accounts.isLoading ? <Spinner /> : null}
        {accounts.data && accounts.data.length === 0 ? (
          <EmptyState title="ยังไม่มีบัญชีทีมงาน" />
        ) : null}

        <ul className="mt-4 divide-y divide-slate-200">
          {accounts.data?.map((account) => {
            const isSelf = account.id === user?.id;
            const isDeleting = remove.isPending && remove.variables?.account.id === account.id;
            const isPreparing = preparingId === account.id;
            return (
              <li
                key={account.id}
                className="flex flex-wrap items-center justify-between gap-3 py-3"
              >
                <div className="min-w-0">
                  <p className="truncate font-semibold">{account.full_name}</p>
                  <p className="truncate text-sm text-slate-500">{account.email}</p>
                  <p className="mt-0.5 text-xs font-medium text-brand-700">
                    {account.role} · {ROLE_LABELS[account.role as "VET" | "STAFF"]}
                  </p>
                </div>
                {isSelf ? (
                  <span className="rounded-full bg-brand-50 px-3 py-1.5 text-xs font-semibold text-brand-700">
                    บัญชีของคุณ
                  </span>
                ) : (
                  <button
                    type="button"
                    className="btn-danger text-xs"
                    disabled={remove.isPending || isPreparing}
                    onClick={() => void openDelete(account)}
                  >
                    {isDeleting ? "กำลังลบ..." : isPreparing ? "กำลังโหลด..." : "ลบบัญชี"}
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      {deleteTarget ? (
        <div
          className="fixed inset-0 z-50 grid place-items-center bg-slate-950/50 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-account-title"
        >
          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-5 shadow-xl dark:bg-slate-900">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 id="delete-account-title" className="text-lg font-bold">
                  จัดการนัดก่อนลบบัญชี
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  {deleteTarget.full_name} ยังมีนัดที่ต้องจัดการ {affected.length} รายการ
                  กรุณาเลือกยกเลิกหรือโอนแต่ละนัด
                </p>
              </div>
              <button
                type="button"
                className="btn-secondary"
                disabled={remove.isPending}
                onClick={() => {
                  setDeleteTarget(null);
                  setAffected([]);
                  setChoices({});
                }}
              >
                ปิด
              </button>
            </div>

            {replacementVets.length === 0 ? (
              <p className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-800">
                ไม่มีสัตวแพทย์คนอื่นให้โอน นัดทั้งหมดจึงต้องเลือกยกเลิก
              </p>
            ) : null}

            <div className="mt-4 space-y-3">
              {affected.map((appointment) => (
                <div
                  key={appointment.appointment_id}
                  className="rounded-xl border border-slate-200 p-3 dark:border-slate-700"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="font-semibold">{appointment.owner_name}</p>
                      <p className="text-sm text-slate-500">
                        {appointment.pet_name} · {formatDateTime(appointment.slot_start)} น.
                      </p>
                    </div>
                    <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-600">
                      {appointment.status}
                    </span>
                  </div>
                  <select
                    className="input mt-3"
                    value={choices[appointment.appointment_id] ?? ""}
                    disabled={remove.isPending}
                    onChange={(event) =>
                      setChoices({
                        ...choices,
                        [appointment.appointment_id]: event.target.value,
                      })
                    }
                  >
                    <option value="" disabled>
                      เลือกการจัดการนัดนี้
                    </option>
                    <option value="CANCEL">ยกเลิกนัด</option>
                    {replacementVets.map((vet) => (
                      <option key={vet.id} value={`TRANSFER:${vet.id}`}>
                        โอนไปยัง {vet.full_name}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>

            <ErrorText error={remove.error} />
            <div className="mt-4 flex flex-wrap justify-end gap-2">
              <button
                type="button"
                className="btn-secondary"
                disabled={remove.isPending}
                onClick={() => {
                  setDeleteTarget(null);
                  setAffected([]);
                  setChoices({});
                }}
              >
                ยกเลิก
              </button>
              <button
                type="button"
                className="btn-danger"
                disabled={!allChosen || remove.isPending}
                onClick={confirmDeleteWithResolutions}
              >
                {remove.isPending ? "กำลังลบบัญชี..." : "ยืนยันลบบัญชี"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
