import type { ChatMessage } from "@/lib/api/types";
import { Markdown } from "@/lib/markdown";
import { cn } from "@/lib/cn";
import { JobCardCarousel } from "@/components/jobs/JobCardList";
import { TailoringCard } from "./TailoringCard";

/** A finished message. User messages are plain bubbles; assistant ones render markdown plus cards. */
export function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end animate-rise">
        <p className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md bg-brand px-4 py-2.5 text-brand-ink">{message.body}</p>
      </div>
    );
  }
  return (
    <div className={cn("space-y-3 animate-rise")}>
      <div className="max-w-[48rem]"><Markdown source={message.body} /></div>
      {message.job_cards.length > 0 ? <JobCardCarousel jobs={message.job_cards} /> : null}
      {message.tailoring_id ? <TailoringCard tailoringId={message.tailoring_id} /> : null}
    </div>
  );
}
