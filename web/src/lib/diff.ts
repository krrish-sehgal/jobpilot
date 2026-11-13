/**
 * Word-level diff built on the classic longest-common-subsequence table.
 * Resume bullets are short (tens of words), so the O(n*m) table is trivial
 * and we avoid pulling in a diff library for one screen.
 */
export type DiffOp = { type: "equal" | "insert" | "delete"; text: string };

/** Splits into words and the whitespace between them, so re-joining the tokens reproduces the input exactly. */
export const tokenize = (s: string): string[] => s.match(/\s+|[^\s]+/g) ?? [];

export function diffWords(before: string, after: string): DiffOp[] {
  const a = tokenize(before);
  const b = tokenize(after);

  // lcs[i][j] = length of the LCS of a[i..] and b[j..]
  const lcs: number[][] = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i--) {
    for (let j = b.length - 1; j >= 0; j--) {
      lcs[i]![j] = a[i] === b[j] ? lcs[i + 1]![j + 1]! + 1 : Math.max(lcs[i + 1]![j]!, lcs[i]![j + 1]!);
    }
  }

  const ops: DiffOp[] = [];
  const push = (type: DiffOp["type"], text: string) => {
    const last = ops[ops.length - 1];
    if (last && last.type === type) last.text += text; // merge runs so the UI renders one span per change
    else ops.push({ type, text });
  };

  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) { push("equal", a[i]!); i++; j++; }
    else if (lcs[i + 1]![j]! >= lcs[i]![j + 1]!) push("delete", a[i++]!);
    else push("insert", b[j++]!);
  }
  while (i < a.length) push("delete", a[i++]!);
  while (j < b.length) push("insert", b[j++]!);
  return ops;
}
