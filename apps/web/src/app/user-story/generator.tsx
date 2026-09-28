"use client";

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";

import {
  DESCRIPTION_MAX,
  DESCRIPTION_MIN,
  type AcceptanceCriterion,
  type UserStory,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

// Uma geracao leva segundos; o dobro do pior caso esperado antes de desistir.
const TIMEOUT_MS = 60000;

const EXAMPLE = "Users cannot export the report.";

type State =
  | { kind: "idle" }
  | { kind: "loading"; startedAt: number }
  | { kind: "error"; message: string }
  | { kind: "done"; story: UserStory };

/**
 * Sem NEXT_PUBLIC_API_URL (hoje, em producao: o backend so e publicado na
 * US-034) o formulario fica desabilitado com um aviso, em vez de falhar a cada
 * clique.
 */
export function Generator() {
  const [description, setDescription] = useState("");
  const [state, setState] = useState<State>({ kind: "idle" });
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const trimmed = description.trim();
  const loading = state.kind === "loading";
  const canSubmit =
    Boolean(API_URL) && !loading && trimmed.length >= DESCRIPTION_MIN;

  async function generate(event: FormEvent) {
    event.preventDefault();
    if (!canSubmit || !API_URL) return;

    const controller = new AbortController();
    controllerRef.current = controller;
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
    setState({ kind: "loading", startedAt: Date.now() });

    try {
      const response = await fetch(`${API_URL}/api/user-story`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description: trimmed }),
        signal: controller.signal,
      });
      const body = await response.json().catch(() => null);
      if (response.ok) {
        setState({ kind: "done", story: body as UserStory });
      } else {
        setState({ kind: "error", message: errorMessage(response.status, body) });
      }
    } catch {
      setState({
        kind: "error",
        message: controller.signal.aborted
          ? "The generation took too long and was cancelled. Try again."
          : "Could not reach the API. Is the backend running?",
      });
    } finally {
      clearTimeout(timer);
    }
  }

  return (
    <div className="mt-10">
      {!API_URL && (
        <p className="mb-6 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-black/70 dark:text-white/70">
          The generator runs locally for now. The backend goes public at the end
          of M1 — until then, clone the repository and run it with your own API
          key.
        </p>
      )}

      <form onSubmit={generate}>
        <label
          htmlFor="description"
          className="text-sm font-medium tracking-wide text-black/50 uppercase dark:text-white/50"
        >
          Problem description
        </label>
        <textarea
          id="description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder={EXAMPLE}
          rows={5}
          maxLength={DESCRIPTION_MAX}
          disabled={!API_URL || loading}
          className="mt-3 block w-full resize-y rounded-xl border border-black/15 bg-transparent px-4 py-3 text-base leading-relaxed placeholder:text-black/35 focus-visible:border-black/40 focus-visible:outline-none disabled:opacity-60 dark:border-white/20 dark:placeholder:text-white/35 dark:focus-visible:border-white/50"
        />
        <div className="mt-4 flex flex-wrap items-center gap-4">
          <button
            type="submit"
            disabled={!canSubmit}
            className="inline-flex items-center gap-2 rounded-lg bg-black px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-black/80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-black disabled:cursor-not-allowed disabled:opacity-40 dark:bg-white dark:text-black dark:hover:bg-white/80 dark:focus-visible:outline-white"
          >
            {loading && (
              <span
                aria-hidden="true"
                className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"
              />
            )}
            {loading ? "Generating…" : "Generate"}
          </button>
          <span className="font-mono text-xs text-black/45 dark:text-white/45">
            {trimmed.length} / {DESCRIPTION_MAX}
          </span>
        </div>
      </form>

      <div aria-live="polite" className="mt-12">
        {state.kind === "loading" && <Loading startedAt={state.startedAt} />}
        {state.kind === "error" && (
          <p
            role="alert"
            className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-black/75 dark:text-white/75"
          >
            {state.message}
          </p>
        )}
        {state.kind === "done" && <StoryView story={state.story} />}
      </div>
    </div>
  );
}

function errorMessage(status: number, body: unknown): string {
  // 422 vem do FastAPI com a lista de erros de validacao em `detail`; uma frase
  // basta, ja que o unico campo e a descricao.
  if (status === 422) {
    return `Describe the problem in ${DESCRIPTION_MIN} to ${DESCRIPTION_MAX.toLocaleString("en")} characters.`;
  }
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  return `The API returned an error (HTTP ${status}). Try again.`;
}

/** Contador visivel: uma tela parada por segundos parece travada. */
function Loading({ startedAt }: { startedAt: number }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const interval = setInterval(
      () => setElapsed(Math.floor((Date.now() - startedAt) / 1000)),
      250,
    );
    return () => clearInterval(interval);
  }, [startedAt]);

  return (
    <div aria-busy="true" className="flex flex-col gap-4">
      <p className="text-sm text-black/60 dark:text-white/60">
        Writing the story and its acceptance criteria — usually 5 to 10 seconds.{" "}
        <span className="font-mono tabular-nums">{elapsed}s</span>
      </p>
      <div className="animate-pulse space-y-3" aria-hidden="true">
        <div className="h-6 w-2/3 rounded bg-black/10 dark:bg-white/10" />
        <div className="h-4 w-full rounded bg-black/5 dark:bg-white/5" />
        <div className="h-4 w-5/6 rounded bg-black/5 dark:bg-white/5" />
        <div className="mt-6 h-28 w-full rounded-xl bg-black/5 dark:bg-white/5" />
      </div>
    </div>
  );
}

function StoryView({ story }: { story: UserStory }) {
  return (
    <article>
      <h2 className="text-2xl font-semibold tracking-tight text-balance">
        {story.title}
      </h2>

      <p className="mt-4 max-w-3xl text-lg leading-relaxed text-black/75 text-pretty dark:text-white/75">
        <Keyword>As a</Keyword> {story.as_a}, <Keyword>I want</Keyword>{" "}
        {story.i_want}, <Keyword>so that</Keyword> {story.so_that.replace(/\.$/, "")}.
      </p>

      <Section title="Acceptance criteria">
        <ol className="space-y-4">
          {story.acceptance_criteria.map((criterion, index) => (
            <li key={index}>
              <Scenario criterion={criterion} />
            </li>
          ))}
        </ol>
      </Section>

      <Section title="Definition of done">
        <BulletList items={story.definition_of_done} />
      </Section>

      {story.edge_cases.length > 0 && (
        <Section title="Edge cases">
          <BulletList items={story.edge_cases} />
        </Section>
      )}
    </article>
  );
}

// Cada passo e uma lista: o primeiro item leva a palavra-chave, os seguintes
// viram "And". O texto do modelo vem sem palavra-chave (veja o schema).
function steps(keyword: string, items: string[]) {
  return items.map((text, index) => ({
    keyword: index === 0 ? keyword : "And",
    text,
  }));
}

function Scenario({ criterion }: { criterion: AcceptanceCriterion }) {
  const lines = [
    ...steps("Given", criterion.given),
    ...steps("When", criterion.when),
    ...steps("Then", criterion.then),
  ];

  return (
    <div className="rounded-xl border border-black/10 p-5 font-mono text-sm leading-relaxed dark:border-white/15">
      <p>
        <span className="font-semibold">Scenario:</span> {criterion.scenario}
      </p>
      <ul className="mt-2 space-y-1">
        {lines.map((line, index) => (
          <li
            key={index}
            className={line.keyword === "And" ? "pl-10" : "pl-4"}
          >
            <span className="font-semibold text-black/55 dark:text-white/55">
              {line.keyword}
            </span>{" "}
            {line.text}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-10">
      <h3 className="text-sm font-medium tracking-wide text-black/50 uppercase dark:text-white/50">
        {title}
      </h3>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed text-black/70 marker:text-black/30 dark:text-white/70 dark:marker:text-white/30">
      {items.map((item, index) => (
        <li key={index}>{item}</li>
      ))}
    </ul>
  );
}

function Keyword({ children }: { children: ReactNode }) {
  return <span className="font-semibold text-black dark:text-white">{children}</span>;
}
