import { useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { homeFor, useAuth } from "../auth/AuthContext";
import { AuthLayout } from "../components/AuthLayout";
import { PasswordField } from "../components/PasswordField";
import { ErrorText, Field, Spinner } from "../components/ui";

export default function LoginPage() {
  const { user, loading, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  if (loading) return <Spinner />;
  if (user) return <Navigate to={homeFor(user.role)} replace />;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const profile = await login(email.trim(), password);
      const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname;
      navigate(from ?? homeFor(profile.role), { replace: true });
    } catch (caught) {
      setError(caught);
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout
      eyebrow="ยินดีต้อนรับกลับ"
      title="เข้าสู่ระบบ"
      subtitle="จัดการนัดหมายและติดตามการรักษาของสัตว์เลี้ยงคุณได้ในที่เดียว"
      headline={
        <>
          ดูแลทุกก้าว
          <br />
          ของสัตว์เลี้ยงของคุณ
        </>
      }
      description="จองนัด ดูคิวสด และติดตามการรักษาได้ตลอดเวลา ไม่ต้องรอสาย"
      features={[
        "จองนัดออนไลน์ได้ตลอด 24 ชั่วโมง",
        "เห็นคิวและเวลาที่คาดว่าจะได้พบสัตวแพทย์",
        "แจ้งเตือนอัตโนมัติ ไม่พลาดนัดสำคัญ",
      ]}
      footer={
        <>
          ยังไม่มีบัญชี?{" "}
          <Link
            to="/register"
            className="font-semibold text-brand-700 hover:text-brand-600 dark:text-brand-300 dark:hover:text-brand-200"
          >
            สมัครสมาชิกฟรี
          </Link>
        </>
      }
    >
      <form className="space-y-4" onSubmit={submit}>
        <Field label="อีเมล">
          <input
            className="input"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
          />
        </Field>

        <PasswordField
          label="รหัสผ่าน"
          value={password}
          onChange={setPassword}
          autoComplete="current-password"
          placeholder="••••••••"
          required
        />

        <ErrorText error={error} />

        <button type="submit" className="btn-primary w-full py-2.5" disabled={busy}>
          {busy ? "กำลังเข้าสู่ระบบ..." : "เข้าสู่ระบบ"}
        </button>
      </form>
    </AuthLayout>
  );
}
