import { createFileRoute } from "@tanstack/react-router";
import { PhoneIntelPage } from "@/pages/PhoneIntelPage";

export const Route = createFileRoute("/phone-intel")({
  component: PhoneIntelPage,
});
