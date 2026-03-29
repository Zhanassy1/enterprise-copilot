import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Тарифы — Enterprise Copilot",
  description: "Планы Free, Pro и Team: лимиты workspace, квоты и сравнение для корпоративных документов.",
};

export default function PricingLayout({ children }: { children: React.ReactNode }) {
  return children;
}
