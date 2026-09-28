// Espelho do UserStory de apps/api/app/user_story.py. Se um mudar, o outro
// muda junto: o backend valida a resposta do modelo contra o modelo Pydantic,
// e esta tela confia nesse formato.

export type AcceptanceCriterion = {
  scenario: string;
  given: string[];
  when: string[];
  then: string[];
};

export type UserStory = {
  title: string;
  as_a: string;
  i_want: string;
  so_that: string;
  acceptance_criteria: AcceptanceCriterion[];
  definition_of_done: string[];
  edge_cases: string[];
};

// Os mesmos limites do UserStoryRequest no backend.
export const DESCRIPTION_MIN = 10;
export const DESCRIPTION_MAX = 4000;
