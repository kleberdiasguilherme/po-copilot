import Link from "next/link";

import { ApiStatus } from "./api-status";
import { HERO_TEXT } from "./hero";

const GITHUB_URL = "https://github.com/kleberdiasguilherme/po-copilot";
const LINKEDIN_URL = "https://www.linkedin.com/in/kleberdiasguilherme/";

type Feature = {
  milestone: string;
  title: string;
  description: string;
  // Presente so nas features ja construidas: vira o selo e o link. O selo diz
  // "runs locally" ate a US-034 publicar o backend; ai passa a "Live".
  href?: string;
};

const features: Feature[] = [
  {
    milestone: "M1",
    title: "User Story Generator",
    href: "/user-story",
    description:
      "Give it a problem statement. It returns a user story with acceptance criteria in Gherkin, a definition of done, and the edge cases you had not thought to ask about.",
  },
  {
    milestone: "M2",
    title: "Feedback Synthesizer",
    description:
      "Drop in tickets, NPS comments or store reviews. Retrieval surfaces the emerging themes, representative quotes and ranked opportunities — every quote traceable to the row it came from.",
  },
  {
    milestone: "M3",
    title: "Backlog Prioritizer",
    description:
      "Feed it a backlog and it returns a RICE score per item with a written rationale. Approve or override any input, and the score recalculates live.",
  },
];

function GitHubIcon() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" className="h-4 w-4 fill-current">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
    </svg>
  );
}

function LinkedInIcon() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" className="h-4 w-4 fill-current">
      <path d="M13.63 13.63h-2.37V9.92c0-.89-.02-2.03-1.24-2.03-1.24 0-1.43.97-1.43 1.97v3.77H6.22V6h2.28v1.04h.03c.32-.6 1.09-1.24 2.25-1.24 2.4 0 2.85 1.58 2.85 3.64v4.19ZM3.55 4.96a1.38 1.38 0 1 1 0-2.76 1.38 1.38 0 0 1 0 2.76Zm1.19 8.67H2.36V6h2.38v7.63ZM14.82 0H1.18C.53 0 0 .52 0 1.16v13.68C0 15.48.53 16 1.18 16h13.64c.65 0 1.18-.52 1.18-1.16V1.16C16 .52 15.47 0 14.82 0Z" />
    </svg>
  );
}

export default function Home() {
  return (
    <div className="flex flex-1 flex-col">
      <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-20 sm:px-8 sm:py-28">
        {/* Hero */}
        <section>
          <p className="inline-flex items-center gap-2 rounded-full border border-black/10 px-3 py-1 text-xs font-medium tracking-wide text-black/60 dark:border-white/15 dark:text-white/60">
            <span
              aria-hidden="true"
              className="h-1.5 w-1.5 rounded-full bg-amber-500"
            />
            In active development — M0, foundation
          </p>

          <h1 className="mt-8 text-4xl font-semibold tracking-tight text-balance sm:text-6xl">
            PO Copilot
          </h1>

          <p className="mt-6 max-w-2xl text-lg leading-relaxed text-black/70 text-pretty sm:text-xl dark:text-white/70">
            {HERO_TEXT}
          </p>

          <div className="mt-10 flex flex-wrap items-center gap-3">
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-lg bg-black px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-black/80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-black dark:bg-white dark:text-black dark:hover:bg-white/80 dark:focus-visible:outline-white"
            >
              <GitHubIcon />
              View the source
            </a>
            <a
              href={LINKEDIN_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-lg border border-black/15 px-5 py-2.5 text-sm font-medium transition-colors hover:bg-black/5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-black dark:border-white/20 dark:hover:bg-white/10 dark:focus-visible:outline-white"
            >
              <LinkedInIcon />
              Kleber Dias Guilherme
            </a>
          </div>
        </section>

        {/* Feature cards */}
        <section aria-labelledby="features-heading" className="mt-24 sm:mt-32">
          <h2
            id="features-heading"
            className="text-sm font-medium tracking-wide text-black/50 uppercase dark:text-white/50"
          >
            What it will do
          </h2>

          <ul className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature) => (
              <li
                key={feature.title}
                className="flex flex-col rounded-xl border border-black/10 p-6 transition-colors hover:border-black/25 dark:border-white/15 dark:hover:border-white/30"
              >
                {feature.href ? (
                  <span className="inline-flex items-center gap-2 font-mono text-xs text-emerald-700 dark:text-emerald-400">
                    <span
                      aria-hidden="true"
                      className="h-1.5 w-1.5 rounded-full bg-emerald-500"
                    />
                    Built — runs locally
                  </span>
                ) : (
                  <span className="font-mono text-xs text-black/45 dark:text-white/45">
                    Planned — {feature.milestone}
                  </span>
                )}
                <h3 className="mt-3 text-lg font-semibold tracking-tight">
                  {feature.title}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-black/65 text-pretty dark:text-white/65">
                  {feature.description}
                </p>
                {feature.href && (
                  <Link
                    href={feature.href}
                    className="mt-5 inline-flex items-center gap-1 self-start text-sm font-medium underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-black dark:focus-visible:outline-white"
                  >
                    Try it <span aria-hidden="true">→</span>
                  </Link>
                )}
              </li>
            ))}
          </ul>
        </section>
      </main>

      <footer className="border-t border-black/10 dark:border-white/15">
        <div className="mx-auto flex w-full max-w-5xl flex-col gap-4 px-6 py-8 text-sm text-black/55 sm:flex-row sm:items-center sm:justify-between sm:px-8 dark:text-white/55">
          <p>
            Built by{" "}
            <a
              href={LINKEDIN_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-4 hover:text-black dark:hover:text-white"
            >
              Kleber Dias Guilherme
            </a>
            . MIT licensed.
          </p>

          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:gap-6">
            <ApiStatus />
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 hover:text-black dark:hover:text-white"
            >
              <GitHubIcon />
              kleberdiasguilherme/po-copilot
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
