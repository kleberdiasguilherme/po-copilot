// Roda com `npm test` (node --test, sem dependencia: o Node tira os tipos).

import assert from "node:assert/strict";
import { test } from "node:test";

import { toJson, toMarkdown } from "./format.ts";
import type { UserStory } from "./types";

// A mesma story de apps/api/tests/fixtures/user_story_valid.json.
const STORY: UserStory = {
  title: "Export filtered report as CSV",
  as_a: "sales manager",
  i_want: "to export the filtered sales report as a CSV file",
  so_that: "I can share the numbers with finance without rebuilding them in a spreadsheet",
  acceptance_criteria: [
    {
      scenario: "Export the current filtered view",
      given: ["I am on the sales report", "I have filtered it to Q3"],
      when: ["I click Export CSV"],
      then: ["a CSV file downloads", "it contains only the Q3 rows"],
    },
    {
      scenario: "Export with no matching rows",
      given: ["my filters match no rows"],
      when: ["I click Export CSV"],
      then: ["a CSV with only the header row downloads"],
    },
    {
      scenario: "Export fails on the server",
      given: ["the export service is unavailable"],
      when: ["I click Export CSV"],
      then: ["I see an error message", "no file downloads"],
    },
  ],
  definition_of_done: [
    "Unit tests cover the CSV serialization",
    "Export event tracked in analytics",
  ],
  edge_cases: [
    "Reports above 100k rows: confirm whether to stream or cap",
    "Values containing commas or line breaks",
  ],
};

const EXPECTED_MARKDOWN = `# Export filtered report as CSV

**As a** sales manager, **I want** to export the filtered sales report as a CSV file, **so that** I can share the numbers with finance without rebuilding them in a spreadsheet.

## Acceptance criteria

\`\`\`gherkin
Scenario: Export the current filtered view
  Given I am on the sales report
  And I have filtered it to Q3
  When I click Export CSV
  Then a CSV file downloads
  And it contains only the Q3 rows

Scenario: Export with no matching rows
  Given my filters match no rows
  When I click Export CSV
  Then a CSV with only the header row downloads

Scenario: Export fails on the server
  Given the export service is unavailable
  When I click Export CSV
  Then I see an error message
  And no file downloads
\`\`\`

## Definition of done

- Unit tests cover the CSV serialization
- Export event tracked in analytics

## Edge cases

- Reports above 100k rows: confirm whether to stream or cap
- Values containing commas or line breaks
`;

test("toMarkdown renders the fixture story", () => {
  assert.equal(toMarkdown(STORY), EXPECTED_MARKDOWN);
});

test("toMarkdown leaves out an empty edge cases section", () => {
  const markdown = toMarkdown({ ...STORY, edge_cases: [] });
  assert.ok(!markdown.includes("Edge cases"));
  assert.ok(markdown.endsWith("- Export event tracked in analytics\n"));
});

test("toMarkdown does not double the final period of so_that", () => {
  const markdown = toMarkdown({ ...STORY, so_that: "finance gets the numbers." });
  assert.ok(markdown.includes("**so that** finance gets the numbers.\n"));
});

test("toMarkdown keeps a line break inside a field on one line", () => {
  const story = structuredClone(STORY);
  story.acceptance_criteria[0].given[0] = "I am on the\nsales report";
  story.edge_cases[0] = "Reports above\n100k rows";
  const markdown = toMarkdown(story);
  assert.ok(markdown.includes("  Given I am on the sales report\n"));
  assert.ok(markdown.includes("- Reports above 100k rows\n"));
});

test("toMarkdown widens the fence when a step contains backticks", () => {
  const story = structuredClone(STORY);
  story.acceptance_criteria[0].then[0] = "the log shows ```done```";
  const markdown = toMarkdown(story);
  assert.ok(markdown.includes("\n````gherkin\n"));
  assert.ok(markdown.includes("\n````\n\n## Definition of done"));
});

test("toJson is the story indented, in schema order", () => {
  assert.equal(toJson(STORY), JSON.stringify(STORY, null, 2) + "\n");
});

test("toJson drops keys that are not part of UserStory", () => {
  const withExtras = {
    prompt_version: "user_story_v1",
    ...STORY,
    acceptance_criteria: STORY.acceptance_criteria.map((c) => ({ ...c, id: 1 })),
  } as UserStory;
  assert.deepEqual(JSON.parse(toJson(withExtras)), STORY);
});
