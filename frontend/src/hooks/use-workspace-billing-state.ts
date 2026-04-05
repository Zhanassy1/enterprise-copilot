"use client";

import { useCallback, useEffect, useState } from "react";
import { api, toErrorMessage, type SubscriptionOut } from "@/lib/api-client";

/** Subscription snapshot for workspace — loading / error aligned for billing-adjacent UI. */
export function useWorkspaceBillingState(workspaceId: string | undefined) {
  const [sub, setSub] = useState<SubscriptionOut | null>(null);
  const [loading, setLoading] = useState(Boolean(workspaceId));
  const [err, setErr] = useState<string | null>(null);

  const reload = useCallback(() => {
    if (!workspaceId) {
      setSub(null);
      setLoading(false);
      setErr(null);
      return;
    }
    setLoading(true);
    setErr(null);
    void api
      .getBillingSubscription()
      .then((s) => {
        setSub(s);
      })
      .catch((e) => {
        const msg = toErrorMessage(e);
        setErr(msg);
        setSub(null);
      })
      .finally(() => setLoading(false));
  }, [workspaceId]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { sub, loading, err, reload };
}
