import type { SelectHTMLAttributes } from "react";

/**
 * Primitive select component with optional label and error message.
 *
 * Mirrors the Input component pattern — label and error are built in
 * so the component is self-contained in simple forms.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.4.
 */

interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  options: SelectOption[];
}

export function Select({
  label,
  error,
  options,
  id,
  className,
  ...props
}: SelectProps) {
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label htmlFor={id} className="text-sm font-medium text-gray-700">
          {label}
        </label>
      )}
      <select
        id={id}
        className={[
          "px-3 py-2 border rounded-md text-sm bg-white",
          "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent",
          error ? "border-red-400" : "border-gray-300",
          className,
        ]
          .filter(Boolean)
          .join(" ")}
        {...props}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
}
