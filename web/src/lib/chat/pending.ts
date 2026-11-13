/**
 * Hand-off for the very first message of a new chat.
 *
 * /app/chat has no conversation id yet. On send it creates the conversation,
 * stashes the message here, and navigates to /app/chat/<id>, where the thread
 * picks it up and streams the reply. A module variable (not storage) is enough
 * because it only needs to survive one client-side navigation.
 *
 * ChatView `peek`s it once into component state on mount, then clears it as
 * soon as it starts sending. State survives Strict Mode's simulated remount, so
 * the second effect run still has the message, while a later visit to the same
 * URL finds nothing pending and loads history instead of re-sending. Resending
 * within one mount is safe because `clientMessageId` makes it idempotent.
 */
export interface PendingMessage {
  body: string;
  clientMessageId: string;
}

const pending = new Map<string, PendingMessage>();

export const setPending = (conversationId: string, msg: PendingMessage) => void pending.set(conversationId, msg);
export const peekPending = (conversationId: string) => pending.get(conversationId);
export const clearPending = (conversationId: string) => void pending.delete(conversationId);
