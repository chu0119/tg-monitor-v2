import { createFileRoute } from "@tanstack/react-router";
import { MonitoringPage } from "@/pages/MonitoringPage";

export const Route = createFileRoute("/monitoring")({
  component: MonitoringPage,
});
