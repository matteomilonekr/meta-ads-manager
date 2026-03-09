# Meta Ads Manager MCP

Server MCP (Model Context Protocol) per le API Meta/Facebook Ads. Gestisci campagne, analytics, audience e creativita direttamente da Claude.

Di **Matteo Milone**. Supporto async completo, modelli tipizzati e 36 tool per la gestione completa di Meta Ads.

## Funzionalita

| Categoria | Tool | Descrizione |
|-----------|------|-------------|
| **Campagne** | 6 | Lista, crea, aggiorna, pausa, riprendi, elimina |
| **Gruppi di inserzioni** | 5 | Lista, crea, aggiorna, pausa, elimina |
| **Inserzioni** | 4 | Lista, crea, aggiorna, elimina |
| **Analytics** | 5 | Insights, confronto (parallelo), export CSV/JSON, trend giornalieri, attribuzione |
| **Audience** | 5 | Custom, lookalike, stima dimensione, elimina |
| **Creativita** | 4 | Lista, crea, carica immagine, anteprima |
| **OAuth** | 5 | URL auth, scambio codice, token long-lived, info token, validazione |
| **Account** | 2 | Lista account pubblicitari, health check |

**36 tool in totale.**

## Guida Rapida

### 1. Installazione

```bash
pip install -e .
```

### 2. Configurazione

```bash
export META_ACCESS_TOKEN="il_tuo_token"

# Opzionale (per flussi OAuth)
export META_APP_ID="il_tuo_app_id"
export META_APP_SECRET="il_tuo_app_secret"
```

### 3. Avvio

```bash
python -m meta_ads_mcp.server
```

### 4. Collegamento a Claude

#### Claude Code (CLI)

Aggiungi al file di configurazione `~/.claude.json`:

```json
{
  "mcpServers": {
    "meta-ads": {
      "command": "python",
      "args": ["-m", "meta_ads_mcp.server"],
      "env": {
        "META_ACCESS_TOKEN": "il_tuo_token"
      }
    }
  }
}
```

#### Claude Desktop

Aggiungi al file `~/.config/claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "meta-ads": {
      "command": "python",
      "args": ["-m", "meta_ads_mcp.server"],
      "env": {
        "META_ACCESS_TOKEN": "il_tuo_token"
      }
    }
  }
}
```

### 5. Installazione da GitHub (senza clonare)

Se non vuoi clonare il repo, puoi installare ed eseguire direttamente da GitHub con `uvx`:

#### Claude Code (CLI)

```json
{
  "mcpServers": {
    "meta-ads": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/matteomilonekr/meta-ads-manager.git", "meta-ads-manager"],
      "env": {
        "META_ACCESS_TOKEN": "il_tuo_token"
      }
    }
  }
}
```

#### Claude Desktop

Stessa configurazione nel file `~/.config/claude/claude_desktop_config.json`.

#### Installazione manuale da GitHub

```bash
pip install git+https://github.com/matteomilonekr/meta-ads-manager.git
meta-ads-manager
```

## Ottenere un Token Meta

1. Vai su [Meta for Developers](https://developers.facebook.com/)
2. Crea un'app (tipo Business)
3. Aggiungi il prodotto **Marketing API**
4. Genera un User Access Token con permessi `ads_management` e `ads_read`
5. Usa il tool `refresh_to_long_lived_token` per estenderlo a 60 giorni

Oppure usa i tool OAuth integrati:

```
generate_auth_url → apri nel browser → exchange_code_for_token → refresh_to_long_lived_token
```

## Riferimento Tool MCP

### Campagne

| Tool | Descrizione |
|------|-------------|
| `list_campaigns` | Lista campagne con filtri stato/obiettivo |
| `create_campaign` | Crea campagna (PAUSED di default) |
| `update_campaign` | Aggiorna nome, stato, budget, pianificazione |
| `pause_campaign` | Metti in pausa una campagna |
| `resume_campaign` | Attiva una campagna in pausa |
| `delete_campaign` | Elimina una campagna |

### Gruppi di Inserzioni

| Tool | Descrizione |
|------|-------------|
| `list_ad_sets` | Lista gruppi per account o campagna |
| `create_ad_set` | Crea gruppo con targeting, budget, ottimizzazione |
| `update_ad_set` | Aggiorna targeting, budget, pianificazione |
| `pause_ad_set` | Metti in pausa un gruppo |
| `delete_ad_set` | Elimina un gruppo |

### Inserzioni

| Tool | Descrizione |
|------|-------------|
| `list_ads` | Lista inserzioni per account, campagna o gruppo |
| `create_ad` | Crea inserzione collegando creativita a gruppo |
| `update_ad` | Aggiorna stato/nome/creativita |
| `delete_ad` | Elimina un'inserzione |

### Analytics

| Tool | Descrizione |
|------|-------------|
| `get_insights` | Metriche performance con intervalli date e breakdown |
| `compare_performance` | Confronta piu oggetti affiancati (async parallelo) |
| `export_insights` | Esporta dati in CSV o JSON |
| `get_daily_trends` | Breakdown giornaliero con direzione trend |
| `get_attribution_data` | Analisi finestra di attribuzione |

### Audience

| Tool | Descrizione |
|------|-------------|
| `list_audiences` | Lista audience custom/lookalike |
| `create_custom_audience` | Crea audience custom (sito web, app, video, ecc.) |
| `create_lookalike` | Crea lookalike da audience sorgente |
| `estimate_audience_size` | Stima copertura per specifiche di targeting |
| `delete_audience` | Elimina un'audience |

### Creativita

| Tool | Descrizione |
|------|-------------|
| `list_creatives` | Lista creativita pubblicitarie |
| `create_creative` | Crea con immagine/video e CTA |
| `upload_image` | Carica immagine da URL, restituisce hash |
| `preview_ad` | Anteprima creativita in vari formati |

### OAuth

| Tool | Descrizione |
|------|-------------|
| `generate_auth_url` | Genera URL OAuth Facebook |
| `exchange_code_for_token` | Scambia codice auth per access token |
| `refresh_to_long_lived_token` | Converti in token 60 giorni |
| `get_token_info` | Validita token, scope, scadenza |
| `validate_token` | Validazione rapida token |

### Account

| Tool | Descrizione |
|------|-------------|
| `list_ad_accounts` | Lista tutti gli account pubblicitari accessibili |
| `health_check` | Controllo connettivita server + API |

## Architettura

```
meta_ads_mcp/
├── server.py          # Server FastMCP con lifespan
├── client.py          # Client httpx async (retry + rate limiting)
├── auth.py            # Gestione token, flussi OAuth
├── models/
│   └── common.py      # Enum, costanti, valori default
├── tools/             # 36 tool MCP (8 moduli)
│   ├── campaigns.py
│   ├── ad_sets.py
│   ├── ads.py
│   ├── analytics.py
│   ├── audiences.py
│   ├── creatives.py
│   ├── oauth.py
│   └── account.py
└── utils/
    ├── errors.py      # Gerarchia errori tipizzati
    ├── rate_limiter.py # Sistema scoring per account
    ├── pagination.py   # Paginazione cursor + URL
    └── formatting.py   # Tabelle Markdown, valute
```

## Stack Tecnologico

- **Python 3.12+**
- **FastMCP** — Framework server MCP
- **httpx** — Client HTTP async
- **Pydantic v2** — Validazione input
- **Meta Graph API v23.0**

## Sviluppo

```bash
# Installa con dipendenze dev
pip install -e ".[dev]"

# Esegui test
pytest -v

# Esegui con coverage
pytest --cov=meta_ads_mcp --cov-report=term-missing
```

## Licenza

Proprietary - Copyright © 2026 Matteo Milone. Tutti i diritti riservati. Vedi [LICENSE.md](LICENSE.md).
