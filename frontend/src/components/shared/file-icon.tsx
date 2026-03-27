import { FileText, FileSpreadsheet, File } from "lucide-react";
import { cn } from "@/lib/utils";

interface FileIconProps {
  type: "PDF" | "DOCX" | "TXT" | "FILE";
  className?: string;
}

const config = {
  PDF: { icon: FileText, color: "text-red-500 bg-red-50" },
  DOCX: { icon: FileSpreadsheet, color: "text-blue-500 bg-blue-50" },
  TXT: { icon: FileText, color: "text-gray-500 bg-gray-100" },
  FILE: { icon: File, color: "text-gray-400 bg-gray-50" },
} as const;

export function FileIcon({ type, className }: FileIconProps) {
  const { icon: Icon, color } = config[type];
  return (
    <div className={cn("flex h-10 w-10 items-center justify-center rounded-xl", color, className)}>
      <Icon className="h-5 w-5" />
    </div>
  );
}
