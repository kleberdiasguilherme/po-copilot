// As duas formas de copiar a story validada (US-007). Logica pura, sem React e
// sem navegador: roda direto no `node --test` (format.test.ts).
//
// So recebe UserStory, nunca PartialUserStory: copiar o parcial entregaria uma
// story que ainda pode falhar na validacao (ADR-006).

import type { AcceptanceCriterion, UserStory } from "./types";

/**
 * Markdown para colar num Jira, Azure DevOps ou Notion sem ajuste: titulo, a
 * frase da story, os cenarios num bloco Gherkin e as listas.
 */
export function toMarkdown(story: UserStory): string {
  const sections = [
    `# ${oneLine(story.title)}`,
    statement(story),
    "## Acceptance criteria",
    gherkinBlock(story.acceptance_criteria),
    "## Definition of done",
    bulletList(story.definition_of_done),
  ];
  // edge_cases pode vir vazio (o schema nao tem minimo): sem titulo solto.
  if (story.edge_cases.length > 0) {
    sections.push("## Edge cases", bulletList(story.edge_cases));
  }
  return sections.join("\n\n") + "\n";
}

/**
 * A story validada, identada. Os campos sao escolhidos um a um, na ordem do
 * schema: qualquer chave a mais que chegue junto no `done` fica de fora.
 */
export function toJson(story: UserStory): string {
  const clean: UserStory = {
    title: story.title,
    as_a: story.as_a,
    i_want: story.i_want,
    so_that: story.so_that,
    acceptance_criteria: story.acceptance_criteria.map((criterion) => ({
      scenario: criterion.scenario,
      given: criterion.given,
      when: criterion.when,
      then: criterion.then,
    })),
    definition_of_done: story.definition_of_done,
    edge_cases: story.edge_cases,
  };
  return JSON.stringify(clean, null, 2) + "\n";
}

function statement(story: UserStory): string {
  const soThat = oneLine(story.so_that).replace(/\.$/, "");
  return `**As a** ${oneLine(story.as_a)}, **I want** ${oneLine(story.i_want)}, **so that** ${soThat}.`;
}

// Um bloco so, cenarios separados por linha em branco: e como um .feature se
// le, e da para colar num arquivo de teste do jeito que esta.
function gherkinBlock(criteria: AcceptanceCriterion[]): string {
  const body = criteria
    .map((criterion) =>
      [
        `Scenario: ${oneLine(criterion.scenario)}`,
        ...steps("Given", criterion.given),
        ...steps("When", criterion.when),
        ...steps("Then", criterion.then),
      ].join("\n"),
    )
    .join("\n\n");
  const fence = fenceFor(body);
  return `${fence}gherkin\n${body}\n${fence}`;
}

// O primeiro passo leva a palavra-chave, os seguintes viram "And" — a mesma
// regra da tela.
function steps(keyword: string, items: string[]): string[] {
  return items.map((text, index) => `  ${index === 0 ? keyword : "And"} ${oneLine(text)}`);
}

function bulletList(items: string[]): string {
  return items.map((item) => `- ${oneLine(item)}`).join("\n");
}

// Uma quebra de linha dentro de um campo quebraria o passo Gherkin ou o item da
// lista em dois.
function oneLine(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}

// Uma sequencia de crases no texto fecharia o bloco antes da hora; a cerca
// sempre tem uma crase a mais que a maior sequencia do conteudo.
function fenceFor(body: string): string {
  const longest = Math.max(0, ...(body.match(/`+/g) ?? []).map((run) => run.length));
  return "`".repeat(Math.max(3, longest + 1));
}
