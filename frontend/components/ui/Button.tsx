import type { ButtonHTMLAttributes, ReactNode } from "react";

/**
 * Primitive button component.
 *
 * Supports primary and secondary variants with disabled state handling.
 * Extends all standard button HTML attributes so it can be used as a
 * submit button, reset button, or trigger button without extra wrappers.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.3.
 */

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  variant?: "primary" | "secondary";
}

export function Button({
  children,
  variant = "primary",
  className,
  ...props
}: ButtonProps) {
  const base =
    "inline-flex items-center justify-center px-4 py-2 rounded-md text-sm font-medium " +
    "transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 " +
    "disabled:opacity-50 disabled:cursor-not-allowed";

  const variants: Record<NonNullable<ButtonProps["variant"]>, string> = {
    primary:
      "bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500",
    secondary:
      "bg-gray-100 text-gray-900 hover:bg-gray-200 focus:ring-gray-400",
  };

  return (
    <button
      className={[base, variants[variant], className].filter(Boolean).join(" ")}
      {...props}
    >
      {children}
    </button>
  );
}
