import React, { Suspense } from "react";
import { Loader2 } from "lucide-react";
import { ReportBuilderClient } from "./ReportBuilderClient";

function ReportBuilderFallback() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-950 text-white">
      <div className="flex flex-col items-center space-y-3">
        <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
        <p className="text-xs font-medium text-zinc-400">Loading stakeholder report...</p>
      </div>
    </div>
  );
}

export default function ReportPage() {
  return (
    <Suspense fallback={<ReportBuilderFallback />}>
      <ReportBuilderClient />
    </Suspense>
  );
}
