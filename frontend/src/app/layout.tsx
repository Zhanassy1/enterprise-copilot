import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

const inter = Inter({ subsets: ["latin", "cyrillic"] });

export const metadata: Metadata = {
  title: "Enterprise Copilot — AI по корпоративным документам",
  description:
    "Multi-tenant поиск и чат по PDF/DOCX с изоляцией workspace, асинхронной индексацией и квотами по плану.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru">
      <body className={`${inter.className} antialiased`}>
        {children}
        <Toaster position="top-right" richColors />
      </body>
    </html>
  );
}
