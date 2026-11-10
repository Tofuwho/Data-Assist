import { Suspense } from "react";
import { Loader2 } from "lucide-react";
import { DatasetExplorerClient } from "./DatasetExplorerClient";

export default function DatasetExplorerPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-zinc-950">
          <div className="flex flex-col items-center space-y-3">
            <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
            <p className="text-xs font-medium text-zinc-400">Loading dataset explorer...</p>
          </div>
        </div>
      }
    >
      <DatasetExplorerClient />
    </Suspense>
  );
}
