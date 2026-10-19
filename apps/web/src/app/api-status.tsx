"use client";

import { useEffect, useState } from "react";

import { wakeApi } from "./wake";

type Status = "checking" | "waking" | "online" | "unreachable";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

const LABELS: Record<Status, string> = {
  checking: "checking API…",
  waking: "waking the API — the free tier sleeps after 15 min…",
  online: "API online",
  unreachable: "API unreachable",
};

const DOTS: Record<Status, string> = {
  checking: "bg-black/25 dark:bg-white/25",
  waking: "animate-pulse bg-amber-500",
  online: "bg-emerald-500",
  unreachable: "bg-red-500",
};

/**
 * Bate no /health do backend e mostra o resultado.
 *
 * Roda no browser de proposito: uma chamada do servidor do Next nao provaria
 * que o CORS entre a Vercel e o Render esta configurado, que e justamente o
 * que costuma quebrar no primeiro deploy.
 *
 * Segunda funcao, nada obvia: e este ping que ACORDA o servidor. O plano
 * gratuito do Render dorme apos 15 min sem trafego e leva ~1 min para voltar
 * (ADR-007). O visitante cai na landing antes de abrir o gerador, e o servidor
 * acorda enquanto ele le a pagina. Remover este selo deixa o primeiro clique em
 * Generate esperando o minuto inteiro.
 *
 * Sem NEXT_PUBLIC_API_URL nao renderiza nada: enquanto o backend nao esta
 * publicado (adiado para o M1), um selo vermelho permanente na landing page
 * seria pior que nenhum selo.
 */
export function ApiStatus() {
  if (!API_URL) return null;
  return <ApiStatusBadge apiUrl={API_URL} />;
}

function ApiStatusBadge({ apiUrl }: { apiUrl: string }) {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    wakeApi(apiUrl, {
      signal: controller.signal,
      onSlow: () => !cancelled && setStatus("waking"),
    }).then((awake) => {
      if (!cancelled) setStatus(awake ? "online" : "unreachable");
    });

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [apiUrl]);

  return (
    <span
      className="inline-flex items-center gap-2"
      aria-live="polite"
      title={`GET ${apiUrl}/health`}
    >
      <span
        aria-hidden="true"
        className={`h-1.5 w-1.5 rounded-full ${DOTS[status]}`}
      />
      {LABELS[status]}
    </span>
  );
}
