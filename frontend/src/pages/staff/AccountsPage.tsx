import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { fieldErrors } from "../../api/client";
import { endpoints } from "../../api/endpoints";
import { pushToast } from "../../components/Toast";
import { ErrorText, Field, PageHeader } from "../../components/ui";

export default function AccountsPage() {
  const [form, setForm] = useState({
    email: "",
    password: "",
    full_name: "",
    phone: "",
    role: "VET" as "VET" | "STAFF",
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
    onSuccess: (user) => {
      pushToast("success", `สร้างบัญชี ${user.role} สำเร็จ: ${user.email}`);
      setForm({ email: "", password: "", full_name: "", phone: "", role: "VET" });
    },
  });

  const errors = fieldErrors(create.error);

  return (
    <div>
      <PageHeader title="สร้างบัญชีสัตวแพทย์ / เจ้าหน้าที่" subtitle="เฉพาะเจ้าหน้าที่เท่านั้นที่สร้างบัญชีทีมงานได้" />

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
    </div>
  );
}
