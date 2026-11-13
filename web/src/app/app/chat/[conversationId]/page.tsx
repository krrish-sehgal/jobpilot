import type { Metadata } from "next";
import { ChatView } from "@/components/chat/ChatView";

export const metadata: Metadata = { title: "Chat" };

export default function ConversationPage({ params }: { params: { conversationId: string } }) {
  // key: switching conversations must reset all stream/composer state.
  return <ChatView key={params.conversationId} conversationId={params.conversationId} />;
}
