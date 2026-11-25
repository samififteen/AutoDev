import { Download, FileDiff } from "lucide-react";
import { useState } from "react";
import { api } from "../services/api";
import { useApiQuery } from "../hooks/useApiQuery";
import { DiffViewer } from "./DiffViewer";
import { Button, ErrorState, Modal, Skeleton } from "./ui";

export function DiffModal({
  executionId,
  onClose,
  initialPath,
}: {
  executionId: number;
  onClose: () => void;
  initialPath?: string | null;
}) {
  const diff = useApiQuery(() => api.diff(executionId), [executionId]);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const download = async () => {
    setDownloading(true);
    setDownloadError(null);
    try {
      await api.downloadPatch(executionId);
    } catch (error) {
      setDownloadError(error instanceof Error ? error.message : "Download failed");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      size="xl"
      title={
        <span className="inline-flex items-center gap-2">
          <FileDiff className="h-4 w-4 text-indigo-300" /> Generated diff
        </span>
      }
      description="Produced from the real git changes in the isolated execution workspace."
      footer={
        <>
          <Button
            variant="secondary"
            icon={Download}
            loading={downloading}
            onClick={download}
          >
            Download .patch
          </Button>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
        </>
      }
    >
      {diff.loading ? (
        <div className="space-y-3">
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : diff.error ? (
        <ErrorState message={diff.error} onRetry={() => void diff.refresh()} />
      ) : diff.data ? (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-500">
            <span>{diff.data.files.length} changed files</span>
            <span className="text-emerald-400">+{diff.data.additions}</span>
            <span className="text-rose-400">-{diff.data.deletions}</span>
            {diff.data.branch ? (
              <span className="mono">
                {diff.data.branch} → {diff.data.base_branch}
              </span>
            ) : null}
          </div>
          {downloadError ? <ErrorState message={downloadError} /> : null}
          <DiffViewer
            files={diff.data.files}
            initialPath={initialPath}
            onDownload={download}
            downloading={downloading}
          />
        </div>
      ) : null}
    </Modal>
  );
}
