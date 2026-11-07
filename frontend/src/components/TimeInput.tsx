type TimeInputProps = {
  value: string;
  onChange: (value: string) => void;
  min?: string;
  max?: string;
  step?: number;
  className?: string;
  required?: boolean;
};

export function TimeInput({
  value,
  onChange,
  min = "09:00",
  max = "17:00",
  step = 1800,
  className = "input",
  required = true,
}: TimeInputProps) {
  return (
    <input
      className={className}
      type="time"
      step={step}
      min={min}
      max={max}
      required={required}
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}
