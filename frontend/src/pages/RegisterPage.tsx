import { useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { homeFor, useAuth } from "../auth/AuthContext";
import { AuthLayout } from "../components/AuthLayout";
import { PasswordField } from "../components/PasswordField";
import { PasswordStrength } from "../components/PasswordStrength";
import { fieldErrors } from "../api/client";
import { ErrorText, Field, Spinner } from "../components/ui";

export default function RegisterPage() {
  const { user, loading, register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    phone: "",
    password: "",
    confirm: "",
  });
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  if (loading) return <Spinner />;
  if (user) return <Navigate to={homeFor(user.role)} replace />;

  const errors = fieldErrors(error);

  const update =
    (key: keyof typeof form) => (event: React.ChangeEvent<HTMLInputElement>) =>
      setForm((current) => ({ ...current, [key]: event.target.value }));

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    if (form.password !== form.confirm) {
      setError(new Error("รหัสผ่านทั้งสองช่องไม่ตรงกัน"));
      return;
    }
    setBusy(true);
    try {
      const profile = await register({
        email: form.email.trim(),
        password: form.password,
        full_name: form.full_name.trim(),
        phone: form.phone.trim() || null,
      });
      navigate(homeFor(profile.role), { replace: true });
    } catch (caught) {
      setError(caught);
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout
      eyebrow="สมัครสมาชิก"
      title="สร้างบัญชีใหม่"
      subtitle="สำหรับเจ้าของสัตว์เลี้ยง — ใช้เวลาไม่ถึง 1 นาที"
      headline={
        <>
          เริ่มต้นดูแล
          <br />
          สัตว์เลี้ยงของคุณวันนี้
        </>
      }
      description="สร้างบัญชีฟรี เพิ่มข้อมูลสัตว์เลี้ยง แล้วจองนัดกับสัตวแพทย์ได้ทันที"
      features={[
        "เพิ่มสัตว์เลี้ยงได้หลายตัวในบัญชีเดียว",
        "ดูประวัติการรักษาย้อนหลังได้ทุกเมื่อ",
        "จัดการนัดหมายได้ง่ายและปลอดภัย",
      ]}
      footer={
        <>
          มีบัญชีแล้ว?{" "}
          <Link
            to="/login"
            className="font-semibold text-brand-700 hover:text-brand-600 dark:text-brand-300 dark:hover:text-brand-200"
          >
            เข้าสู่ระบบ
          </Link>
        </>
      }
    >
      <form className="space-y-3.5" onSubmit={submit}>
        <Field label="ชื่อ-นามสกุล" error={errors.full_name}>
          <input
            className="input"
            required
            value={form.full_name}
            onChange={update("full_name")}
            placeholder="สมชาย ใจดี"
          />
        </Field>

        <Field label="อีเมล" error={errors.email}>
          <input
            className="input"
            type="email"
            autoComplete="email"
            required
            value={form.email}
            onChange={update("email")}
            placeholder="you@example.com"
          />
        </Field>

        <Field label="เบอร์โทร (ไม่บังคับ)" error={errors.phone}>
          <input
            className="input"
            inputMode="tel"
            value={form.phone}
            onChange={update("phone")}
            placeholder="0812345678"
          />
        </Field>

        <PasswordField
          label="รหัสผ่าน (อย่างน้อย 8 ตัวอักษร)"
          value={form.password}
          onChange={(value) => setForm((current) => ({ ...current, password: value }))}
          autoComplete="new-password"
          placeholder="••••••••"
          error={errors.password}
          required
          minLength={8}
          hint={<PasswordStrength password={form.password} />}
        />

        <PasswordField
          label="ยืนยันรหัสผ่าน"
          value={form.confirm}
          onChange={(value) => setForm((current) => ({ ...current, confirm: value }))}
          autoComplete="new-password"
          placeholder="••••••••"
          required
        />

        <ErrorText error={error} />

        <button type="submit" className="btn-primary w-full py-2.5" disabled={busy}>
          {busy ? "กำลังสมัคร..." : "สมัครสมาชิก"}
        </button>
      </form>
    </AuthLayout>
  );
}
