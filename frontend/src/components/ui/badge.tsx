/**
 * Badge — small inline label used for status and priority chips.
 *
 * Uses class-variance-authority (cva) to define variants without Radix primitives,
 * since shadcn's badge component is purely CSS — there is no @radix-ui/react-badge package.
 */

import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors",
  {
    variants: {
      variant: {
        default: "bg-slate-100 text-slate-800",
        open: "bg-blue-50 text-blue-700",
        in_progress: "bg-amber-50 text-amber-700",
        in_review: "bg-purple-50 text-purple-700",
        closed: "bg-green-50 text-green-700",
        low: "bg-green-50 text-green-700",
        medium: "bg-yellow-50 text-yellow-700",
        high: "bg-orange-50 text-orange-700",
        critical: "bg-red-50 text-red-700",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
