import clsx, { type ClassValue } from "clsx";

/** Tiny alias so components read `cn("a", cond && "b")`. */
export const cn = (...inputs: ClassValue[]) => clsx(inputs);
