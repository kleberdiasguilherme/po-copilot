# Deploy

| Parte | Onde | Custo | Status |
|---|---|---|---|
| Frontend (`apps/web`) | Vercel Hobby | US$0 | No ar desde o M0 |
| Backend (`apps/api`) | Render, plano gratuito (`render.yaml`) | US$0 | US-034 — decisão no ADR-007 |

A escolha de hospedagem e a estratégia de custo são uma decisão só, registrada no [ADR-007](adr/ADR-007-free-hosting-and-cost-guards.md). Em resumo: nenhum gasto novo; o Render gratuito roda uma instância só, e é isso que mantém válidos o limite por IP e a cota diária em memória.

## A ordem importa

Cada lado precisa da URL do outro:

1. **Render primeiro.** O `render.yaml` já traz a URL da Vercel em `CORS_ORIGINS`, então o CORS sai certo no primeiro deploy. O deploy gera a URL da API.
2. **Vercel depois**, com a URL da API em `NEXT_PUBLIC_API_URL`, e um redeploy.

## 1. Render — backend

1. Em <https://render.com>, entre com o GitHub. **Se em algum momento pedir cartão, pare**: a premissa do ADR-007 deixou de valer.
2. **New → Blueprint**, escolha o repositório `kleberdiasguilherme/po-copilot`. O Render lê o `render.yaml` da raiz.
3. Ele pede o valor de `ANTHROPIC_API_KEY` (no arquivo, `sync: false`). Cole a chave ali. Ela fica só no painel, nunca no git.
4. Confirme. O build roda `pip install -r requirements.txt` em `apps/api`, e o serviço sobe sem `--proxy-headers`: o IP do visitante vem do `CF-Connecting-IP` (ADR-007).

O que o `render.yaml` já define, para não preencher à mão:

| Campo | Valor |
|---|---|
| Plano | `free` |
| Região | `virginia` |
| Root directory | `apps/api` |
| Start | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Healthcheck | `/health` |
| `PYTHON_VERSION` | `3.13.13` |
| `ENVIRONMENT` | `production` |
| `CORS_ORIGINS` | `https://po-copilot-kleberdias.vercel.app` |

Os limites de custo têm padrão no código (`app/config.py`) e podem ser trocados por variável no painel, sem commit:

| Variável | Padrão | O que limita |
|---|---|---|
| `DAILY_GENERATION_QUOTA` | `20` | gerações por dia, somando todos os visitantes |
| `RATE_LIMIT_REQUESTS` | `3` | gerações por IP na janela |
| `RATE_LIMIT_WINDOW_SECONDS` | `3600` | a janela do limite por IP |

Confirme:

```bash
curl https://<sua-api>.onrender.com/health
# {"status":"ok","version":"0.1.0","environment":"production"}
```

Se `environment` vier `development`, as variáveis não chegaram ao processo.

**O plano gratuito dorme** depois de 15 minutos sem tráfego e leva cerca de um minuto para acordar. O primeiro `curl` depois disso demora; é esperado.

## 2. Vercel — frontend

No projeto da Vercel (Root Directory `apps/web`), adicione:

| Variável | Valor |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://<sua-api>.onrender.com`, **sem barra no fim** |

E faça um redeploy. O prefixo `NEXT_PUBLIC_` embute o valor no bundle **durante o build**: sem um build novo, nada muda.

Com a variável no build:

- o selo do User Story Generator na landing passa a **Live**, com a bolinha verde;
- o rodapé mostra o status da API. Esse ping também **acorda o servidor** enquanto o visitante lê a página.

Os domínios de preview da Vercel (`po-copilot-<hash>.vercel.app`) não estão em `CORS_ORIGINS`. Nos previews, o status vai mostrar *API unreachable*. É esperado.

## 3. Anthropic Console — o teto físico

O saldo pré-pago só é teto se **a recarga automática estiver desligada**. Confira em Billing antes de abrir o link ao público.

## Verificação final

- [ ] `curl https://<api>/health` devolve 200 com `"environment":"production"`
- [ ] A landing mostra o selo **Live** e, no rodapé, **API online**
- [ ] O console do browser não tem erro de CORS
- [ ] `/user-story` gera uma story em produção
- [ ] Nenhuma chave commitada: `ANTHROPIC_API_KEY` só existe no painel do Render
- [ ] Recarga automática desligada no Anthropic Console
