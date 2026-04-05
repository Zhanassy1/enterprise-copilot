/**
 * Canonical ingestion job / document pipeline phases.
 * Keep in sync with backend/app/constants/ingestion.py (INGESTION_JOB_STATUSES).
 */
export const PIPELINE_JOB_STATUSES = [
  "queued",
  "processing",
  "retrying",
  "ready",
  "failed",
] as const;

export type PipelineJobStatus = (typeof PIPELINE_JOB_STATUSES)[number];
