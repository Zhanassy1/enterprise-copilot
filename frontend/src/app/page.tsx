"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { isAuthenticated } from "@/lib/auth";

export default function RootPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace(isAuthenticated() ? "/documents" : "/login");
  }, [router]);
  return null;
}
