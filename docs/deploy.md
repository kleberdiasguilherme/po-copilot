# Deploy

| Parte | Onde | Status |
|---|---|---|
| Frontend (`apps/web`) | Vercel Hobby (US$0) | **No ar desde o M0** |
| Backend (`apps/api`) | Railway ou Vercel Python Functions | **Adiado para o M1** — issue US-009 |

## Hoje — M0: só o frontend

O backend não foi publicado no M0 por decisão consciente: hoje ele serve apenas `/health`, que nenhum visitante abre, e não vale pagar hospedagem para isso. Ele sobe no M1, quando o User Story Generator existir. A escolha entre Railway (~US$1–5/mês) e Python Functions na própria Vercel (grátis, mas muda o que o ADR-000 registrou) é parte da US-009.

Importe o repositório `kleberdiasguilherme/po-copilot` na Vercel:

| Configuração | Valor |
|---|---|
| Framework Preset | Next.js (detectado) |
| Root Directory | `apps/web` — o passo que todo mundo erra em monorepo |
| Variáveis de ambiente | **nenhuma** |

Sem `NEXT_PUBLIC_API_URL`, o `ApiStatus` não renderiza nada: o rodapé fica sem selo, em vez de mostrar *API unreachable* para sempre. A cada push em `main` a Vercel redeploya sozinha.

Verificação:

- [ ] A URL pública devolve 200 (`curl -sI <url>`)
- [ ] A landing page carrega com hero, os 3 feature cards e os links
- [ ] O rodapé **não** mostra selo de status da API

## Depois — M1: backend (runbook preservado)

> Nada abaixo está em uso hoje. É o runbook para quando a US-009 for executada, supondo Railway. Se a decisão for Vercel Python Functions, esta seção muda. Com o frontend já publicado, o passo 2 vira só "adicionar `NEXT_PUBLIC_API_URL` na Vercel e redeployar".

Depois do primeiro deploy, os dois serviços redeployam sozinhos a cada push em `main`.


### A ordem importa

Cada serviço precisa da URL do outro, e nenhuma das duas existe antes do primeiro deploy. A saída é deployar em três passos, em vez de dois:

1. **Railway primeiro**, com o CORS ainda apontando só para `localhost`. Isso gera a URL da API.
2. **Vercel depois**, já com a URL da Railway em mãos. Isso gera a URL do site.
3. **Voltar à Railway** e pôr a URL da Vercel em `CORS_ORIGINS`.

Pular o passo 3 é o erro clássico: o site carrega, a API responde ao `curl`, e mesmo assim o indicador no rodapé fica em *API unreachable* — porque o browser bloqueia a resposta antes de o JavaScript vê-la.

### 1. Railway — backend

Novo projeto a partir do repositório `kleberdiasguilherme/po-copilot`.

| Configuração | Valor |
|---|---|
| Root Directory | `apps/api` |
| Build / Start | vêm do `apps/api/railway.json` — não preencha à mão |
| Healthcheck | `/health`, já declarado no mesmo arquivo |

O `railway.json` sobe com `--port $PORT`. A Railway injeta essa variável e ela **não** é 8000; porta fixa no código é o motivo mais comum de um serviço subir e ficar inacessível.

Variáveis de ambiente:

| Variável | Valor no primeiro deploy | Depois do passo 3 |
|---|---|---|
| `ENVIRONMENT` | `production` | `production` |
| `CORS_ORIGINS` | `http://localhost:3000` | `https://<seu-site>.vercel.app` |
| `ANTHROPIC_API_KEY` | deixe vazia | vazia até o M1 |

Gere o domínio público em **Settings → Networking → Generate Domain** e confirme:

```bash
curl https://<sua-api>.up.railway.app/health
# {"status":"ok","version":"0.1.0","environment":"production"}
```

Se `environment` vier `development`, a variável não chegou ao processo.

### 2. Vercel — frontend

Importe o mesmo repositório.

| Configuração | Valor |
|---|---|
| Framework Preset | Next.js (detectado) |
| Root Directory | `apps/web` |

Variável de ambiente:

| Variável | Valor |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://<sua-api>.up.railway.app` — **sem barra no fim** |

O prefixo `NEXT_PUBLIC_` faz o Next embutir o valor no bundle **durante o build**. Mudar essa variável depois não tem efeito nenhum até um novo build — não basta reiniciar.

### 3. Railway de novo — liberar o CORS

Troque `CORS_ORIGINS` pela URL da Vercel e redeploye. Aceita mais de uma origem, separadas por vírgula:

```
https://po-copilot.vercel.app,http://localhost:3000
```

Manter `localhost:3000` na lista permite apontar o front local para a API de produção quando precisar.

Os domínios de preview da Vercel (`po-copilot-<hash>.vercel.app`) mudam a cada PR e **não** estarão nessa lista — nos previews o indicador vai mostrar *API unreachable*. É esperado.

### Verificação final

- [ ] `curl https://<api>/health` devolve 200 com `"environment":"production"`
- [ ] A landing page carrega na URL da Vercel
- [ ] O rodapé mostra **API online** (não *checking* nem *unreachable*)
- [ ] O console do browser não tem erro de CORS
- [ ] Nenhuma chave real commitada — `ANTHROPIC_API_KEY` só existe nos painéis

O terceiro item é o que fecha o end-to-end: ele só fica verde se o browser conseguiu falar com a Railway a partir do domínio da Vercel.
