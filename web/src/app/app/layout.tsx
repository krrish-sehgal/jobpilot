import type { ReactNode } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { RequireAuth } from "@/components/layout/RequireAuth";
import { ConversationListProvider } from "@/hooks/useConversationList";

/** Everything under /app: signed-in only, with the sidebar shell. */
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <RequireAuth>
      <ConversationListProvider>
        <AppShell>{children}</AppShell>
      </ConversationListProvider>
    </RequireAuth>
  );
}
