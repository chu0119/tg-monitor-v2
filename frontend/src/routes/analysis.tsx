import { createFileRoute } from "@tanstack/react-router";
import { AnalysisPage } from "@/pages/AnalysisPage";

export const Route = createFileRoute("/analysis")({
  component: AnalysisPage,
});
