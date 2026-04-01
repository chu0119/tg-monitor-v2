import { createFileRoute } from "@tanstack/react-router";
import { ProxyPage } from "@/pages/ProxyPage";

export const Route = createFileRoute("/proxy")({
  component: ProxyPage,
});
