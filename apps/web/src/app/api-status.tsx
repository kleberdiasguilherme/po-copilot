"use client";

import { useEffect, useState } from "react";

type Status = "checking" | "online" | "unreachable";

const API_URL = process.env.NEXT_PUBLIC_API_URL;
const TIMEOUT_MS = 8000;

const LABELS: Record<Status, string> = {
  checking: "checking API…",
  online: "API online",
  unreachable: "API unreachable",
};

const DOTS: Record<Status, string> = {
  checking: "bg-black/25 dark:bg-white/25",
  online: "bg-emerald-500",
  unreachable: "bg-red-500",
};

/**
 * Bate no /health do backend e mostra o resultado.
 *
 * Roda no browser de proposito: uma chamada do servidor do Next nao provaria
 * que o CORS entre a Vercel e a Railway esta configurado, que e justamente o
 * que costuma quebrar no primeiro deploy.
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
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

    fetch(`${apiUrl}/health`, { signal: controller.signal })
      .then((response) => {
        if (!cancelled) setStatus(response.ok ? "online" : "unreachable");
      })
      .catch(() => {
        if (!cancelled) setStatus("unreachable");
      })
      .finally(() => clearTimeout(timer));

    return () => {
      cancelled = true;
      clearTimeout(timer);
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
