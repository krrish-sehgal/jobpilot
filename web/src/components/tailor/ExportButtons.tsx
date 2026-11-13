"use client";

import { useState } from "react";
import { Download } from "lucide-react";
import { api, isMockMode } from "@/lib/api";
import { describeError } from "@/lib/api/errors";
import type { ExportFormat } from "@/lib/api/types";
import { Button } from "@/components/ui/Button";

/**
 * Downloads go through fetch (not a plain link) because the endpoint needs the
 * Authorization header; the blob is then saved via a temporary object URL.
 */
export function ExportButtons({ tailoringId, settled }: { tailoringId: string; settled: () => Promise<unknown> }) {
  const [busy, setBusy] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function download(format: ExportFormat) {
    setBusy(format);
    setError(null);
    try {
      await settled(); // export must reflect the decisions the user just made
      const { blob, fileName } = await api.exportTailoring(tailoringId, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = fileName;
      // Some browsers ignore clicks on detached links; revoke late so the download can start.
      document.body.append(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => download("pdf")} loading={busy === "pdf"} disabled={busy !== null} icon={<Download className="h-4 w-4" aria-hidden />}>Export PDF</Button>
        <Button variant="secondary" onClick={() => download("docx")} loading={busy === "docx"} disabled={busy !== null} icon={<Download className="h-4 w-4" aria-hidden />}>{isMockMode ? "Export Word (RTF)" : "Export DOCX"}</Button>
      </div>
      {error ? <p role="alert" className="mt-2 text-sm text-bad">{error}</p> : null}
    </div>
  );
}
