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
 */
export function ApiStatus() {
  // Sem a variavel nao ha o que checar: ja nasce no estado final, em vez de
  // um setState sincrono dentro do efeito.
  const [status, setStatus] = useState<Status>(
    API_URL ? "checking" : "unreachable",
  );

  useEffect(() => {
    if (!API_URL) return;

    let cancelled = false;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

    fetch(`${API_URL}/health`, { signal: controller.signal })
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
  }, []);

  return (
    <span
      className="inline-flex items-center gap-2"
      aria-live="polite"
      title={API_URL ? `GET ${API_URL}/health` : "NEXT_PUBLIC_API_URL is not set"}
    >
      <span
        aria-hidden="true"
        className={`h-1.5 w-1.5 rounded-full ${DOTS[status]}`}
      />
      {LABELS[status]}
    </span>
  );
}
