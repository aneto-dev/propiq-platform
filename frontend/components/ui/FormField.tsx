import type { ReactNode } from "react";

/**
 * Generic form field wrapper — label + child + optional error message.
 *
 * Used to label any form control (Input, Select, custom widget) consistently.
 * For Input and Select, the label prop on those components handles simple cases;
 * FormField is used when a child needs external labelling (e.g. grouped controls).
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.4.
 */

interface FormFieldProps {
  label: string;
  htmlFor?: string;
  error?: string;
  required?: boolean;
  children: ReactNode;
}

export function FormField({
  label,
  htmlFor,
  error,
  required,
  children,
}: FormFieldProps) {
  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor={htmlFor}
        className="text-sm font-medium text-gray-700"
      >
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      {children}
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
}
