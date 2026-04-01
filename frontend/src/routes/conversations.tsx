import { createFileRoute } from "@tanstack/react-router";
import { ConversationsPage } from "@/pages/ConversationsPage";

export const Route = createFileRoute("/conversations")({
  component: ConversationsPage,
});
