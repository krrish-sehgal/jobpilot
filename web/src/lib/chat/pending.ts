/**
 * Hand-off for the very first message of a new chat.
 *
 * /app/chat has no conversation id yet. On send it creates the conversation,
 * stashes the message here, and navigates to /app/chat/<id>, where the thread
 * picks it up and streams the reply. A module variable (not storage) is enough
 * because it only needs to survive one client-side navigation.
 *
 * We `peek` rather than `take`, and clear after the turn finishes: React Strict
 * Mode runs effects twice in development, and the second run must still find
 * the message. Resending is safe because `clientMessageId` makes it idempotent.
 */
export interface PendingMessage {
  body: string;
  clientMessageId: string;
}

const pending = new Map<string, PendingMessage>();

export const setPending = (conversationId: string, msg: PendingMessage) => void pending.set(conversationId, msg);
export const peekPending = (conversationId: string) => pending.get(conversationId);
export const clearPending = (conversationId: string) => void pending.delete(conversationId);
