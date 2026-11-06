interface PasswordStrengthResult {
  score: 1 | 2 | 3 | 4;
  label: string;
  tips: string[];
}

const BAR_COLORS: Record<1 | 2 | 3 | 4, string> = {
  1: "bg-rose-500",
  2: "bg-amber-500",
  3: "bg-brand-500",
  4: "bg-emerald-600",
};

const TEXT_COLORS: Record<1 | 2 | 3 | 4, string> = {
  1: "text-rose-600",
  2: "text-amber-600",
  3: "text-brand-700",
  4: "text-emerald-700",
};

export function getPasswordStrength(password: string): PasswordStrengthResult | null {
  if (!password) return null;

  const hasLength = password.length >= 8;
  const hasLong = password.length >= 12;
  const hasMixedCase = /[a-z]/.test(password) && /[A-Z]/.test(password);
  const hasDigit = /\d/.test(password);
  const hasSymbol = /[^A-Za-z0-9]/.test(password);

  const tips: string[] = [];
  if (!hasLength) tips.push("ใช้อย่างน้อย 8 ตัวอักษร");
  if (!hasMixedCase) tips.push("ผสมตัวพิมพ์ใหญ่และตัวพิมพ์เล็ก");
  if (!hasDigit) tips.push("เพิ่มตัวเลข");
  if (!hasSymbol) tips.push("เพิ่มอักขระพิเศษ เช่น ! @ #");
  if (hasLength && !hasLong) tips.push("ใช้ 12 ตัวอักษรขึ้นไปเพื่อความปลอดภัยที่มากขึ้น");

  if (!hasLength) return { score: 1, label: "สั้นเกินไป", tips };

  const points = [hasLength, hasLong, hasMixedCase, hasDigit, hasSymbol].filter(Boolean).length;
  const score: 1 | 2 | 3 | 4 = points >= 5 ? 4 : points >= 4 ? 3 : points >= 2 ? 2 : 1;
  const label =
    score === 4 ? "แข็งแรงมาก" : score === 3 ? "แข็งแรง" : score === 2 ? "ปานกลาง" : "อ่อน";

  return { score, label, tips };
}

export function PasswordStrength({ password }: { password: string }) {
  const result = getPasswordStrength(password);
  if (!result) return null;

  const { score, label, tips } = result;

  return (
    <div className="mt-2" aria-live="polite">
      <div
        className="flex gap-1"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={4}
        aria-valuenow={score}
        aria-label={`ความแข็งแรงของรหัสผ่าน: ${label}`}
      >
        {[1, 2, 3, 4].map((step) => (
          <span
            key={step}
            className={`h-1.5 flex-1 rounded-full transition-colors ${
              step <= score ? BAR_COLORS[score] : "bg-slate-200 dark:bg-slate-700"
            }`}
          />
        ))}
      </div>

      <div className="mt-1.5 flex items-center justify-between gap-2">
        <span className={`text-xs font-medium ${TEXT_COLORS[score]}`}>{label}</span>
        {score === 4 ? (
          <span className="text-xs text-slate-400 dark:text-slate-500">พร้อมใช้งาน</span>
        ) : null}
      </div>

      {tips.length > 0 ? (
        <ul className="mt-1 space-y-0.5 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
          {tips.slice(0, 3).map((tip) => (
            <li key={tip}>• {tip}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
