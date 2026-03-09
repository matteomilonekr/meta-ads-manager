# Changelog

Tutte le modifiche rilevanti al progetto Meta Ads MCP Server sono documentate in questo file.

---

## [1.1.0] — 2026-03-09

### Security Fix

#### CRITICA — SSRF in upload_image (`creatives.py`)
- Aggiunta funzione `_validate_image_url()` che blocca:
  - Schemi non HTTP/HTTPS (file://, ftp://, gopher://)
  - Hostname localhost, 127.0.0.1, 0.0.0.0, [::1]
  - IP privati (10.x, 172.16.x, 192.168.x), loopback, riservati, link-local
- Disabilitato `follow_redirects` nel fallback httpx
- Aggiunto catch specifico `(httpx.HTTPError, MetaAdsMCPError)` al posto di `except Exception`
- Rimosso leak di errore nel messaggio di ritorno

#### ALTA — Information disclosure in errori HTTP (`client.py`)
- Rimosso `response.text[:500]` dal messaggio di errore
- Ora restituisce: `"HTTP {status}: Non-JSON error response from Meta API."`

#### ALTA — Token leak in log/output (`oauth.py`)
- `logger.error` ora logga solo `type(exc).__name__`, non l'eccezione completa
- Return all'utente ora generico: `"Token is invalid or expired. Please check your META_ACCESS_TOKEN."`

#### MEDIA — Validazione special_ad_categories (`campaigns.py`)
- Aggiunta whitelist: `EMPLOYMENT`, `HOUSING`, `CREDIT`, `ISSUES_ELECTIONS_POLITICS`
- Valori non validi restituiscono errore prima della chiamata API

#### MEDIA — JSON validation con error handling (`ad_sets.py`)
- `json.loads()` su targeting e promoted_object ora in `try/except json.JSONDecodeError`
- Messaggio di errore chiaro restituito all'utente

#### BASSA — Validazione account ID (`_helpers.py`)
- `normalize_account_id()` ora verifica che la parte dopo `act_` sia numerica
- Raise `ValueError` su input malformato

### Safety — Protezione Anti-Ban

#### Nuovo modulo `utils/safety.py`
- Classe `SafetyGuard` con sliding window di 1 ora
- Limiti per account:
  - 25 creazioni/ora (campagne + ad set + ads + audience + creative)
  - 40 cambi di stato/ora (pause/resume/activate)
  - 15 modifiche budget/ora
  - 2s cooldown tra operazioni di scrittura
- Warning automatico all'80% del limite
- Blocco automatico al 100% con messaggio in italiano

#### Integrazione in tutti i tool di scrittura
- `campaigns.py` — create, update, pause, resume, delete
- `ad_sets.py` — create, update, pause, delete
- `ads.py` — create, update, delete
- `audiences.py` — create_custom, create_lookalike, delete
- `creatives.py` — create_creative

### File creati

| File | Descrizione |
|------|-------------|
| `.env.example` | Template variabili d'ambiente |
| `meta_ads_mcp/utils/safety.py` | Modulo protezione anti-ban |
| `CHANGELOG.md` | Questo file |

### File modificati

- `meta_ads_mcp/tools/creatives.py`
- `meta_ads_mcp/client.py`
- `meta_ads_mcp/tools/oauth.py`
- `meta_ads_mcp/tools/campaigns.py`
- `meta_ads_mcp/tools/ad_sets.py`
- `meta_ads_mcp/tools/ads.py`
- `meta_ads_mcp/tools/audiences.py`
- `meta_ads_mcp/tools/_helpers.py`
- `LICENSE.md`

---

## [1.0.0] — 2026-02

### Release iniziale
- Server MCP per Meta (Facebook) Ads API
- Tool completi: campagne, ad set, ads, creative, audience, analytics
- OAuth flow integrato
- Rate limiting per account
- Export insights CSV/JSON
