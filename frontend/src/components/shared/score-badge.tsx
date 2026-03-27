import { Badge } from "@/components/ui/badge";

interface ScoreBadgeProps {
  score: number;
}

export function ScoreBadge({ score }: ScoreBadgeProps) {
  const pct = Math.round(score * 100);
  const variant = pct >= 70 ? "default" : pct >= 40 ? "secondary" : "outline";
  return <Badge variant={variant}>{pct}%</Badge>;
}
