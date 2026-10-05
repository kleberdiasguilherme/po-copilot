// Roda com `npm test`. O fetch e falso: nenhum servidor de verdade.
//
// A ordem dos testes importa: o modulo lembra quando o servidor respondeu, e o
// segundo teste depende do primeiro ter acordado o servidor.

import assert from "node:assert/strict";
import { test } from "node:test";

import { wakeApi } from "./wake.ts";

const API = "https://api.example.test";

function html(): Response {
  return new Response("<html>Service waking up</html>", {
    status: 200,
    headers: { "Content-Type": "text/html" },
  });
}

function health(): Response {
  return Response.json({ status: "ok", version: "0.1.0", environment: "production" });
}

test("wakeApi retries past the loading page and a dropped request until /health answers", async () => {
  const answers: (() => Response)[] = [
    html, // a pagina de carregamento do Render: 200, mas nao e o /health
    () => {
      throw new TypeError("Failed to fetch");
    },
    health,
  ];
  const calls: string[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    calls.push(String(input));
    return answers[calls.length - 1]();
  }) as typeof fetch;
  let slow = 0;

  const awake = await wakeApi(API, { onSlow: () => slow++ });

  assert.equal(awake, true);
  assert.deepEqual(calls, [`${API}/health`, `${API}/health`, `${API}/health`]);
  assert.equal(slow, 1, "a demora vira aviso na tela, uma vez");
});

test("wakeApi skips the check right after the server answered", async () => {
  globalThis.fetch = (async () => {
    throw new Error("should not be called");
  }) as typeof fetch;

  assert.equal(await wakeApi(API), true);
});
