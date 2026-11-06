import { useId, useState } from "react";
import type { ReactNode } from "react";

interface PasswordFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: string;
  placeholder?: string;
  error?: string;
  required?: boolean;
  minLength?: number;
  hint?: ReactNode;
}

function EyeIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-5 w-5"
      aria-hidden="true"
    >
      <path d="M2.25 12S6 5.25 12 5.25 21.75 12 21.75 12 18 18.75 12 18.75 2.25 12 2.25 12Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-5 w-5"
      aria-hidden="true"
    >
      <path d="m3 3 18 18" />
      <path d="M10.6 5.4A9.8 9.8 0 0 1 12 5.25c6 0 9.75 6.75 9.75 6.75a18 18 0 0 1-2.4 3.3" />
      <path d="M6.2 6.2A17.7 17.7 0 0 0 2.25 12S6 18.75 12 18.75c1.2 0 2.3-.27 3.3-.72" />
      <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
    </svg>
  );
}

export function PasswordField({
  label,
  value,
  onChange,
  autoComplete,
  placeholder,
  error,
  required,
  minLength,
  hint,
}: PasswordFieldProps) {
  const id = useId();
  const [visible, setVisible] = useState(false);
  const toggleLabel = visible ? "ซ่อนรหัสผ่าน" : "แสดงรหัสผ่าน";

  return (
    <div>
      <label htmlFor={id} className="label">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          className="input pr-11"
          type={visible ? "text" : "password"}
          autoComplete={autoComplete}
          required={required}
          minLength={minLength}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${id}-error` : undefined}
        />
        <button
          type="button"
          onClick={() => setVisible((current) => !current)}
          aria-label={toggleLabel}
          aria-pressed={visible}
          aria-controls={id}
          title={toggleLabel}
          className="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-r-xl text-slate-400 transition hover:text-slate-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-500 dark:hover:text-slate-200"
        >
          {visible ? <EyeOffIcon /> : <EyeIcon />}
        </button>
      </div>
      {error ? (
        <span id={`${id}-error`} className="mt-1 block text-xs text-rose-600 dark:text-rose-300">
          {error}
        </span>
      ) : null}
      {hint}
    </div>
  );
}
