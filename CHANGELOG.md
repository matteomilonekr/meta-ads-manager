# Changelog

Tutte le modifiche rilevanti al progetto Meta Ads MCP Server sono documentate in questo file.

---

## [1.3.0] — 2026-11-03

### Aggiornamento API Meta v26.0

- Versione dell'API portata da v23.0 a v26.0 (per il Marketing API la v23.0 è scaduta il 9 giugno 2026 e anche la v24.0 è a fine vita). L'URL del grafo, quello dei video e il numero mostrato da `health_check` derivano ora da un'unica costante.
- `create_campaign`: la categoria speciale `CREDIT` è stata sostituita da Meta con `FINANCIAL_PRODUCTS_SERVICES` (gennaio 2025). Il nuovo valore è accettato; `CREDIT` resta valido e viene convertito in automatico. Aggiunta anche `ONLINE_GAMBLING_AND_GAMING`.
- `create_campaign`: nuovo parametro `special_ad_category_country` (codici ISO a 2 lettere separati da virgola, es. `IT`). Per `ISSUES_ELECTIONS_POLITICS` è obbligatorio e senza paese la funzione risponde con un errore prima di chiamare Meta; per casa, lavoro e prodotti finanziari, se omesso, Meta usa il paese fiscale dell'inserzionista.
- `create_campaign`: quando il budget non è sulla campagna ma sui gruppi di inserzioni, viene inviato `is_adset_budget_sharing_enabled` (obbligatorio dalla v24.0). Nuovo parametro `adset_budget_sharing` (predefinito `False`: ogni gruppo spende solo il proprio budget; `True` è la scelta consigliata da Meta e consente di condividere fino al 20% del budget tra i gruppi della campagna). Il campo non viene inviato se la campagna ha un budget.
- `create_ad_set`: non richiede più il campo `budget_rebalance_flag` (deprecato da Meta dalla v7.0). Il rilevamento del budget a livello campagna usa solo `daily_budget` e `lifetime_budget`, quindi il comportamento non cambia.
- `create_creative`: `page_id`, `video_id` e `instagram_user_id` tornano a essere stringhe nello schema del tool. Un numero intero è accettato solo se esatto (fino a 2^53-1); decimali, booleani e numeri più grandi, che dai client JavaScript arrivano già arrotondati, vengono rifiutati con un errore chiaro invece di mandare a Meta un ID sbagliato.
- `upload_image`: con `file_path` il file deve essere un vero JPEG o PNG (controllo del contenuto, non solo dell'estensione), non vuoto, non un collegamento simbolico e al massimo di 10 MB; con `META_UPLOAD_DIR` impostata deve stare in quella cartella. Passa dalla protezione anti-ban come gli altri caricamenti, restituisce errori leggibili se Meta rifiuta l'immagine e non accetta `image_url` e `file_path` insieme.
- Client: lettura delle intestazioni di utilizzo di Meta (`X-Business-Use-Case-Usage`, `X-Ad-Account-Usage`, `X-App-Usage`). Quando Meta segnala un blocco, le chiamate per quell'account si fermano e l'errore indica quanti minuti attendere invece di ritentare alla cieca. Tutti i codici di limite documentati (4, 17, 32, 613, 80000-80014) sono riconosciuti.
- `estimate_audience_size`: usa `estimate_mau_lower_bound` e `estimate_mau_upper_bound`, perché `daily_outcomes_curve` è stato rimosso dalla v26.0 (su tutte le versioni dal 27 ottobre 2026) e il tool restituiva sempre N/A.
- `create_lookalike`: il paese non viene più inviato, perché dal 1 settembre 2026 Meta lo ignora e crea un lookalike senza paese (la consegna segue i paesi del gruppo di inserzioni). Il parametro `country` resta facoltativo per non rompere le chiamate esistenti.
- Test: nuovi file `tests/test_campaigns_v26.py`, `tests/test_creatives_upload.py`, `tests/test_rate_limits.py`, `tests/test_audiences_v26.py`.

---

## [1.2.0] — 2026-10-13

### Nuove funzioni

- `upload_video`: carica un video dal computer nella libreria dell'account pubblicitario (caricamento a pezzi, va bene anche per file grandi) e restituisce l'ID video e la miniatura quando Meta ha finito di elaborarlo.
- `get_creative`: legge una creatività completa (pagina, account Instagram, video, testo, CTA, opzioni Advantage+), utile per copiare l'impostazione di un annuncio esistente.
- `create_creative`: per i video il link ora è facoltativo (annunci di copertura senza pulsante), nuovi parametri `instagram_user_id`, `thumbnail_url` e `opt_out_enhancements`.

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
