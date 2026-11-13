const PROMPTS = [
  "Show me remote backend roles",
  "Entry-level data analyst jobs",
  "Senior product roles in Singapore",
  "Find an internship that uses Python",
];

/** Empty-state starters. Clicking one sends it immediately. */
export function SuggestedPrompts({ onPick, disabled }: { onPick: (text: string) => void; disabled: boolean }) {
  return (
    <div className="flex flex-wrap justify-center gap-2" role="group" aria-label="Suggested prompts">
      {PROMPTS.map((p) => (
        <button
          key={p}
          type="button"
          disabled={disabled}
          onClick={() => onPick(p)}
          className="rounded-full border border-line bg-surface px-4 py-2 text-sm hover:border-brand hover:text-brand disabled:opacity-50"
        >
          {p}
        </button>
      ))}
    </div>
  );
}
