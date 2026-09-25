import type { Metadata } from "next";
import Link from "next/link";

import { Generator } from "./generator";

export const metadata: Metadata = {
  title: "User Story Generator — PO Copilot",
  description:
    "Describe a problem and get a user story with Gherkin acceptance criteria, a definition of done and edge cases.",
};

export default function UserStoryPage() {
  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-16 sm:px-8 sm:py-20">
      <Link
        href="/"
        className="text-sm text-black/55 underline-offset-4 hover:text-black hover:underline dark:text-white/55 dark:hover:text-white"
      >
        ← PO Copilot
      </Link>

      <h1 className="mt-8 text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
        User Story Generator
      </h1>
      <p className="mt-4 max-w-2xl text-base leading-relaxed text-black/70 text-pretty dark:text-white/70">
        Describe the problem in a sentence or two. You get back a user story, 3
        to 5 acceptance criteria in Gherkin, a definition of done, and the edge
        cases worth asking about.
      </p>

      <Generator />
    </main>
  );
}
