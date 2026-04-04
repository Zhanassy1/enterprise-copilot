"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { InviteAcceptance } from "@/components/invite/invite-acceptance";
import { Loader2 } from "lucide-react";

function InviteQueryRedirect() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [redirecting, setRedirecting] = useState(token.length >= 16);

  useEffect(() => {
    if (token.length >= 16) {
      router.replace(`/invite/${encodeURIComponent(token)}`);
    } else {
      setRedirecting(false);
    }
  }, [token, router]);

  if (redirecting && token.length >= 16) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950">
        <Loader2 className="h-10 w-10 animate-spin text-indigo-400" />
      </div>
    );
  }

  return <InviteAcceptance token={token} />;
}

export default function InvitePage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-slate-950">
          <Loader2 className="h-10 w-10 animate-spin text-indigo-400" />
        </div>
      }
    >
      <InviteQueryRedirect />
    </Suspense>
  );
}
