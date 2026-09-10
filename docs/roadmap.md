# PO Copilot — Roadmap

**Projeto:** PO Copilot — Assistente PO/PM com RAG e IA Generativa
**Gerente do Projeto:** Kleber Dias Guilherme
**Data de início (kickoff):** 14/09/2026 — âncora anterior de 31/08 abandonada com 0h executadas; reancorado em 10/09/2026
**Escopo V1 decidido:** vertical slice — M0 + M1 primeiro, decisão de escalar para M2/M3 ao fim da Semana 2
**Nível do produto:** MVP demo público, sem auth e sem multi-tenancy
**Carga semanal:** variável (6-15h) — burndown recalibrado com horas reais a cada semana
**Duração estimada:** 7 semanas (~70-100h totais)
**Repositório:** https://github.com/kleberdiasguilherme/po-copilot (a criar)
**Live demo:** https://po-copilot.vercel.app (a criar)

---

## Visão

Uma plataforma que atua como copiloto do Product Owner / Product Manager, gerando user stories, sintetizando feedback de cliente e apoiando priorização de backlog através de RAG (Retrieval-Augmented Generation) e modelos de linguagem.

## Objetivo Estratégico

**Curto prazo:** portfolio piece diferenciado para candidaturas de PM/PO no mercado japonês, cobrindo skills preferenciais (RAG, LLMOps, liderança de projeto, fine-tuning).

**Médio prazo:** base extensível que pode virar SaaS real ou ser open-sourced.

## Fases de Alto Nível

| Fase | Semanas | Milestone | Skill construída |
|---|---|---|---|
| **M0 — Fundação** | Semana 1 | Setup completo + arquitetura documentada | Engenharia sênior |
| **M1 — First Feature (US Generator)** | Semana 2 | User Story Generator funcional | LLM apps + prompt engineering |
| **M2 — RAG + Feedback Synth** | Semanas 3-4 | RAG rodando + Feedback Synthesizer live | **RAG** |
| **M3 — Backlog Prioritizer** | Semanas 5-6 | RICE score assistente funcional | LLMOps (observabilidade, custos) |
| **M4 — Fine-tuning (opcional)** | Semana 7 | Classifier fine-tuned de feedback | **Fine-tuning + distillation** |

---

## Milestones detalhados

### M0 — Fundação (Semana 1 · 10-12h)

Objetivo: repositório inicializado, arquitetura clara, deploy pipeline funcionando.

**Entregas:**
- Repositório GitHub público com README profissional
- Monorepo Next.js (front) + FastAPI (back)
- CI/CD via GitHub Actions
- Deploy pipeline: Vercel + Railway
- Documentação de arquitetura (ADR-000 base)
- Landing page simples com "coming soon"

### M1 — User Story Generator (Semana 2 · 10-15h)

Objetivo: primeira feature end-to-end funcional, sem RAG ainda.

**Entregas:**
- UI simples: textarea para descrição de problema + botão gerar
- Backend: endpoint POST /api/user-story
- Prompt engineering: prompt versionado que gera user story + AC em Gherkin
- Integração com Claude API (Anthropic)
- Rate limiting básico
- Deploy funcionando em URL pública

**Aprendizado:** LLM app anatomy, structured output, prompt versioning.

### M2 — RAG + Feedback Synthesizer (Semanas 3-4 · 20-25h)

Objetivo: RAG rodando, primeira feature RAG-powered.

**Entregas:**
- pgvector setup (Neon ou Supabase)
- Ingestão: upload de CSV/JSON de feedback → embedding
- LangChain retrieval chain funcionando
- UI de upload + query
- Backend: endpoint POST /api/synthesize-feedback
- Output: temas emergentes, quotes destacados, oportunidades de produto
- Documentação técnica do RAG (ADR-001)

**Aprendizado:** RAG completo, embeddings, vector search, chunking, retrieval-augmented prompts.

### M3 — Backlog Prioritizer + Observabilidade (Semanas 5-6 · 15-20h)

Objetivo: terceira feature + observabilidade em produção.

**Entregas:**
- UI: upload de backlog em CSV/JSON
- Backend: endpoint POST /api/prioritize-backlog
- RAG combina: backlog itens + contexto histórico + feedback
- Output: RICE score sugerido para cada item + justificativa
- **Observabilidade:** PostHog para uso, Sentry para erros, custom dashboard de custos Anthropic
- **LLMOps:** guardrails, retry logic, fallback, prompt caching
- Documentação técnica de LLMOps (ADR-002)

**Aprendizado:** LLMOps sério — observabilidade, custo, guardrails, produção real.

### M4 — Fine-tuning Classifier (Semana 7 · 15-20h) — OPCIONAL

Objetivo: cobrir a 4ª skill guardada (fine-tuning + distillation).

**Entregas:**
- Dataset: 500-1000 exemplos rotulados de feedback (bug / feature / praise / churn)
- Fine-tune de BERT-small ou DistilBERT em Google Colab
- Integração ao pipeline do Feedback Synthesizer
- Comparação: LLM classifier vs. fine-tuned classifier (accuracy, latência, custo)
- Documentação técnica (ADR-003)
- Blog post técnico opcional

**Aprendizado:** fine-tuning na prática + distillation + trade-offs de arquitetura.

---

## Fluxo entre milestones

```
M0 (Setup)
  └─ M1 (User Story Gen) — habilita padrão LLM
       └─ M2 (RAG + Feedback Synth) — habilita RAG pattern
            └─ M3 (Backlog Prioritizer + LLMOps) — habilita produção
                 └─ M4 (Fine-tune, opcional) — cobre skill extra
```

Cada milestone tem valor isolado — mesmo se parar em M2 ou M3, o portfolio já é forte.

---

## Riscos identificados (ver `PO_Copilot_Riscos.xlsx`)

Top 3:
1. **Custo Claude API sair do orçamento** — mitigação: prompt caching + limite de rate
2. **Time em paralelo com aplicações de emprego** — mitigação: milestones pequenos, cada um entregável isolado
3. **Aprendizado LangChain mais lento que estimado** — mitigação: fallback pra chamadas diretas HTTP se necessário

---

## Definição de sucesso

Ao final de M3 (mínimo), o projeto entrega:

- ✅ URL pública funcional (com pelo menos 3 features)
- ✅ GitHub público com README profissional + arquitetura documentada
- ✅ Case study em PDF (2-3 páginas) para colar em cover letter
- ✅ Vídeo demo de 3 minutos (Loom) para email de aplicação
- ✅ Menção verificável no LinkedIn como projeto pessoal
- ✅ Skills demonstráveis: RAG, LLMOps, engenharia end-to-end, product thinking

Ao final de M4 (extended), inclui:

- ✅ Skill adicional: fine-tuning + distillation
- ✅ Blog post técnico opcional
- ✅ Base para conversar em interview sobre trade-offs de arquitetura AI

---

## Métricas semanais (ver `PO_Copilot_Burndown.xlsx`)

- Horas planejadas vs. executadas
- Milestones completados vs. planejados
- Custo real (Anthropic + hosting) vs. orçamento
- Bloqueios ativos
