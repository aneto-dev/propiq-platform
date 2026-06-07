import type { InputHTMLAttributes } from "react";

/**
 * Primitive input component with optional label and error message.
 *
 * Extends all standard input HTML attributes. The label is paired with
 * the input via htmlFor/id for accessibility.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.3.
 */

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export function Input({ label, error, id, className, ...props }: InputProps) {
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label htmlFor={id} className="text-sm font-medium text-gray-700">
          {label}
        </label>
      )}
      <input
        id={id}
        className={[
          "px-3 py-2 border rounded-md text-sm",
          "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent",
          "placeholder:text-gray-400",
          error ? "border-red-400" : "border-gray-300",
          className,
        ]
          .filter(Boolean)
          .join(" ")}
        {...props}
      />
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
}
