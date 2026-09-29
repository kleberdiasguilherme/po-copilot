"use client";

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";

import {
  DESCRIPTION_MAX,
  DESCRIPTION_MIN,
  type AcceptanceCriterion,
  type PartialUserStory,
  type UserStory,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

// Sem nenhum byte novo por este tempo, a geracao e dada como travada. Com
// streaming o relogio zera a cada trecho: uma geracao longa mas viva nao cai.
const IDLE_TIMEOUT_MS = 20000;

const EXAMPLE = "Users cannot export the report.";

type State =
  | { kind: "idle" }
  | { kind: "loading"; startedAt: number }
  | { kind: "streaming"; startedAt: number; story: PartialUserStory }
  | { kind: "error"; message: string; story?: PartialUserStory }
  | { kind: "done"; story: UserStory };

type StreamEvent = { event: string; data: unknown };

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
  useFirstContentMeasure(state);

  const trimmed = description.trim();
  const busy = state.kind === "loading" || state.kind === "streaming";
  const canSubmit =
    Boolean(API_URL) && !busy && trimmed.length >= DESCRIPTION_MIN;

  async function generate(event: FormEvent) {
    event.preventDefault();
    if (!canSubmit || !API_URL) return;

    const controller = new AbortController();
    controllerRef.current = controller;
    let timer = setTimeout(() => controller.abort(), IDLE_TIMEOUT_MS);
    const keepAlive = () => {
      clearTimeout(timer);
      timer = setTimeout(() => controller.abort(), IDLE_TIMEOUT_MS);
    };

    const startedAt = Date.now();
    performance.clearMarks(CLICK_MARK);
    performance.mark(CLICK_MARK);
    setState({ kind: "loading", startedAt });

    // O ultimo parcial recebido: se o stream falhar, ele fica na tela com o erro.
    let story: PartialUserStory | undefined;

    try {
      const response = await fetch(`${API_URL}/api/user-story/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description: trimmed }),
        signal: controller.signal,
      });
      // 422, 429 e 503 saem antes do stream abrir, como JSON comum.
      if (!response.ok || !response.body) {
        const body = await response.json().catch(() => null);
        setState({ kind: "error", message: errorMessage(response.status, body) });
        return;
      }

      for await (const { event, data } of readEvents(response.body, keepAlive)) {
        if (event === "partial") {
          story = data as PartialUserStory;
          // O carregamento continua ate haver algo para ler.
          if (hasText(story)) setState({ kind: "streaming", startedAt, story });
        } else if (event === "done") {
          logFieldOrder(story);
          setState({ kind: "done", story: (data as { story: UserStory }).story });
          return;
        } else if (event === "error") {
          setState({ kind: "error", message: errorMessage(502, data), story });
          return;
        }
      }
      // O stream terminou sem `done` nem `error`: a conexao caiu no meio.
      setState({
        kind: "error",
        message: "The connection dropped before the story was complete. Try again.",
        story,
      });
    } catch {
      setState({
        kind: "error",
        message: controller.signal.aborted
          ? story
            ? "The generation stopped responding before it finished. Try again."
            : "The generation took too long and was cancelled. Try again."
          : story
            ? "The connection dropped before the story was complete. Try again."
            : "Could not reach the API. Is the backend running?",
        story,
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
          disabled={!API_URL || busy}
          className="mt-3 block w-full resize-y rounded-xl border border-black/15 bg-transparent px-4 py-3 text-base leading-relaxed placeholder:text-black/35 focus-visible:border-black/40 focus-visible:outline-none disabled:opacity-60 dark:border-white/20 dark:placeholder:text-white/35 dark:focus-visible:border-white/50"
        />
        <div className="mt-4 flex flex-wrap items-center gap-4">
          <button
            type="submit"
            disabled={!canSubmit}
            className="inline-flex items-center gap-2 rounded-lg bg-black px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-black/80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-black disabled:cursor-not-allowed disabled:opacity-40 dark:bg-white dark:text-black dark:hover:bg-white/80 dark:focus-visible:outline-white"
          >
            {busy && (
              <span
                aria-hidden="true"
                className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"
              />
            )}
            {busy ? "Generating…" : "Generate"}
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
        {state.kind === "streaming" && (
          <Provisional status="generating" startedAt={state.startedAt}>
            <StoryView story={state.story} provisional />
          </Provisional>
        )}
        {state.kind === "error" && state.story && hasText(state.story) && (
          <Provisional status="incomplete">
            <StoryView story={state.story} provisional />
          </Provisional>
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

/** O intervalo antes do primeiro trecho legivel: o mesmo estado de antes. */
function Loading({ startedAt }: { startedAt: number }) {
  return (
    <div aria-busy="true" className="flex flex-col gap-4">
      <p className="text-sm text-black/60 dark:text-white/60">
        Writing the story and its acceptance criteria — usually 5 to 10 seconds.
        <Elapsed startedAt={startedAt} />
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

/** Contador visivel: uma tela parada por segundos parece travada. */
function Elapsed({ startedAt }: { startedAt: number }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const interval = setInterval(
      () => setElapsed(Math.floor((Date.now() - startedAt) / 1000)),
      250,
    );
    return () => clearInterval(interval);
  }, [startedAt]);

  return <span className="ml-1.5 font-mono tabular-nums normal-case">{elapsed}s</span>;
}

/**
 * Renderiza tanto a story validada quanto o parcial que ainda chega: cada parte
 * aparece quando o primeiro trecho dela chega, e cresce dali.
 */
function StoryView({
  story,
  provisional = false,
}: {
  story: PartialUserStory;
  provisional?: boolean;
}) {
  const scenarios = (story.acceptance_criteria ?? []).filter(
    (criterion) => criterion.scenario,
  );

  return (
    <article>
      {story.title && (
        <h2 className="text-2xl font-semibold tracking-tight text-balance">
          {story.title}
        </h2>
      )}

      {story.as_a !== undefined && (
        <p className="mt-4 max-w-3xl text-lg leading-relaxed text-black/75 text-pretty dark:text-white/75">
          <Keyword>As a</Keyword> {story.as_a}
          {story.i_want !== undefined && (
            <>
              , <Keyword>I want</Keyword> {story.i_want}
            </>
          )}
          {story.so_that !== undefined && (
            <>
              , <Keyword>so that</Keyword> {story.so_that.replace(/\.$/, "")}
              {/* Ponto final so quando a frase acabou de chegar. */}
              {!provisional && "."}
            </>
          )}
        </p>
      )}

      {scenarios.length > 0 && (
        <Section title="Acceptance criteria">
          <ol className="space-y-4">
            {scenarios.map((criterion, index) => (
              <li key={index}>
                <Scenario criterion={criterion} />
              </li>
            ))}
          </ol>
        </Section>
      )}

      {story.definition_of_done && story.definition_of_done.length > 0 && (
        <Section title="Definition of done">
          <BulletList items={story.definition_of_done} />
        </Section>
      )}

      {story.edge_cases && story.edge_cases.length > 0 && (
        <Section title="Edge cases">
          <BulletList items={story.edge_cases} />
        </Section>
      )}
    </article>
  );
}

/**
 * Moldura do conteudo nao validado (ADR-006). Enquanto gera, avisa que aquilo
 * ainda nao e definitivo: quem le um sexto cenario e depois recebe erro de
 * validacao precisa ter sido avisado antes. Se o stream falha, o conteudo fica,
 * marcado como incompleto, junto da mensagem de erro.
 */
function Provisional({
  status,
  startedAt,
  children,
}: {
  status: "generating" | "incomplete";
  startedAt?: number;
  children: ReactNode;
}) {
  const generating = status === "generating";

  return (
    <div
      aria-busy={generating}
      className={`mt-6 rounded-xl border border-dashed p-5 first:mt-0 sm:p-6 ${
        generating
          ? "border-amber-500/60 bg-amber-500/5"
          : "border-red-500/50 bg-red-500/5 opacity-75"
      }`}
    >
      <p className="mb-5 flex items-center gap-2 text-xs font-medium tracking-wide text-black/55 uppercase dark:text-white/55">
        <span
          aria-hidden="true"
          className={`h-2 w-2 rounded-full ${
            generating ? "animate-pulse bg-amber-500" : "bg-red-500"
          }`}
        />
        {generating ? (
          <>
            Generating — not final until it finishes
            {startedAt !== undefined && <Elapsed startedAt={startedAt} />}
          </>
        ) : (
          "Incomplete — this is not a valid story"
        )}
      </p>
      {children}
    </div>
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

function Scenario({ criterion }: { criterion: Partial<AcceptanceCriterion> }) {
  const lines = [
    ...steps("Given", criterion.given ?? []),
    ...steps("When", criterion.when ?? []),
    ...steps("Then", criterion.then ?? []),
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

/**
 * Le o corpo em Server-Sent Events. EventSource nao serve: so faz GET, e a
 * descricao vai no corpo de um POST. `onChunk` roda a cada trecho recebido.
 */
async function* readEvents(
  body: ReadableStream<Uint8Array>,
  onChunk: () => void,
): AsyncGenerator<StreamEvent> {
  const reader = body.getReader();
  // stream: true guarda um caractere multibyte cortado entre dois trechos.
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) return;
    onChunk();
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let end: number;
    while ((end = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      let event = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (data) yield { event, data: JSON.parse(data) };
    }
  }
}

/** Ha algo para ler: qualquer string nao vazia, em qualquer campo. */
function hasText(value: unknown): boolean {
  if (typeof value === "string") return value.trim().length > 0;
  if (Array.isArray(value)) return value.some(hasText);
  if (value && typeof value === "object") return Object.values(value).some(hasText);
  return false;
}

// Medicao da AC da US-006 ("primeiro trecho em menos de 3s"): do clique em
// Generate ate o primeiro conteudo legivel pintado na tela, e nao o primeiro
// byte do JSON. Fica no painel Performance do DevTools como "first-content".
const CLICK_MARK = "generate-click";
const DEV = process.env.NODE_ENV !== "production";

function useFirstContentMeasure(state: State) {
  const measured = useRef(false);

  useEffect(() => {
    if (state.kind === "loading") measured.current = false;
    if (state.kind !== "streaming" || measured.current) return;
    measured.current = true;
    // O efeito roda depois do commit; o proximo frame ja vem depois da pintura.
    requestAnimationFrame(() => {
      const entry = performance.measure("first-content", CLICK_MARK);
      if (DEV) console.info(`[po-copilot] first-content ms=${Math.round(entry.duration)}`);
    });
  }, [state]);
}

// A ordem em que os campos chegaram no stream: a das chaves do JSON gerado.
function logFieldOrder(story: PartialUserStory | undefined) {
  if (DEV && story) console.info(`[po-copilot] field-order ${Object.keys(story).join(",")}`);
}
