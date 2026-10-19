// O backend roda no plano gratuito do Render, que dorme depois de 15 minutos
// sem trafego e leva cerca de um minuto para acordar (ADR-007). Este modulo e o
// unico lugar que sabe disso: o ApiStatus da landing e o gerador o usam para
// acordar o servidor e dizer ao visitante o que esta acontecendo.

// Sem resposta por este tempo, o servidor provavelmente esta dormindo: a tela
// passa a dizer isso, em vez de parecer travada.
export const WAKE_HINT_MS = 2500;

// O Render diz "about one minute"; o dobro cobre um acordar lento sem deixar o
// visitante esperando para sempre.
const WAKE_TIMEOUT_MS = 120_000;
const ATTEMPT_TIMEOUT_MS = 30_000;
const RETRY_DELAY_MS = 2000;

// Uma resposta recente prova que o servidor esta de pe, e ele so dorme depois
// de 15 minutos: dentro desta margem, nao ha por que checar de novo.
const AWAKE_FOR_MS = 10 * 60_000;

let lastAwakeAt = 0;

/** Registra que o servidor acabou de responder. */
export function markAwake() {
  lastAwakeAt = Date.now();
}

/**
 * Garante o servidor de pe: repete o /health ate ele responder, ou ate o tempo
 * acabar. `onSlow` roda se a primeira resposta demorar mais que WAKE_HINT_MS.
 * Devolve false se o servidor nao acordou a tempo.
 */
export async function wakeApi(
  apiUrl: string,
  { onSlow, signal }: { onSlow?: () => void; signal?: AbortSignal } = {},
): Promise<boolean> {
  if (Date.now() - lastAwakeAt < AWAKE_FOR_MS) return true;

  const slow = setTimeout(() => onSlow?.(), WAKE_HINT_MS);
  const deadline = Date.now() + WAKE_TIMEOUT_MS;
  try {
    while (Date.now() < deadline && !signal?.aborted) {
      if (await healthy(apiUrl, signal)) {
        markAwake();
        return true;
      }
      await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
    }
    return false;
  } finally {
    clearTimeout(slow);
  }
}

async function healthy(apiUrl: string, signal?: AbortSignal): Promise<boolean> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ATTEMPT_TIMEOUT_MS);
  const abort = () => controller.abort();
  signal?.addEventListener("abort", abort);
  try {
    const response = await fetch(`${apiUrl}/health`, {
      signal: controller.signal,
      cache: "no-store",
    });
    if (!response.ok) return false;
    // Enquanto acorda, o Render pode devolver a propria pagina de carregamento.
    // So conta o JSON do /health de verdade.
    const body = (await response.json().catch(() => null)) as { status?: unknown } | null;
    return body?.status === "ok";
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", abort);
  }
}
