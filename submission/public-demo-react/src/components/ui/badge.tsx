import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../../lib/utils";

const badgeVariants = cva("inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-bold uppercase tracking-[0.12em]", {
  variants: {
    variant: {
      default: "border-primary/20 bg-primary/10 text-primary",
      amber: "border-amber-400/30 bg-amber-400/10 text-amber-700",
      violet: "border-violet-400/30 bg-violet-400/10 text-violet-700",
      neutral: "border-border bg-secondary text-muted-foreground"
    }
  },
  defaultVariants: { variant: "default" }
});

export function Badge({ className, variant, children }: React.HTMLAttributes<HTMLDivElement> & VariantProps<typeof badgeVariants>) {
  return <div className={cn(badgeVariants({ variant }), className)}>{children}</div>;
}
