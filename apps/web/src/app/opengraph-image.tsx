import { ImageResponse } from "next/og";

import { HERO_TEXT } from "./hero";

export const alt = "PO Copilot — a RAG assistant for Product Owners";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// Mesmas cores da landing page (globals.css, tema claro). Sem fonte
// customizada de proposito: carregar fonte externa no ImageResponse exige
// buscar o arquivo no build e e a causa mais comum de erro nessa API.
const FOREGROUND = "#171717";
const BACKGROUND = "#ffffff";

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "80px 96px",
          background: BACKGROUND,
          color: FOREGROUND,
        }}
      >
        <div style={{ fontSize: 96, fontWeight: 600, letterSpacing: "-0.04em" }}>
          PO Copilot
        </div>
        <div
          style={{
            marginTop: 32,
            fontSize: 34,
            lineHeight: 1.45,
            color: "rgba(0, 0, 0, 0.7)",
          }}
        >
          {HERO_TEXT}
        </div>
        <div
          style={{
            marginTop: 56,
            display: "flex",
            alignItems: "center",
            fontSize: 24,
            color: "rgba(0, 0, 0, 0.6)",
          }}
        >
          <div
            style={{
              width: 12,
              height: 12,
              borderRadius: 9999,
              background: "#f59e0b",
              marginRight: 14,
            }}
          />
          In active development
        </div>
      </div>
    ),
    size,
  );
}
