# Meta Ads MCP Server - Istruzioni per Claude Code

Questo progetto e' un server MCP per Meta (Facebook) Ads. Usa i tool `mcp__meta-ads__*` per interagire con le API.

## Regola fondamentale: PIANIFICA PRIMA, ESEGUI DOPO

**NON creare MAI campagne, ad set, ads o audience senza aver prima pianificato e ottenuto conferma dall'utente.**

### Processo obbligatorio per operazioni di creazione/modifica

1. **Fai domande** — Prima di qualsiasi azione, raccogli le informazioni mancanti. Chiedi in modo conversazionale, non come un modulo. Se l'utente ha gia' fornito alcune info nel messaggio, non richiederle. Possibili domande:
   - Su quale account vuoi operare? (mostra lista se necessario)
   - Qual e' l'obiettivo? (lead, vendite, traffico, awareness...)
   - Chi vuoi raggiungere? (eta', genere, paese, interessi)
   - Quanto vuoi spendere al giorno?
   - Hai gia' la creative pronta (immagine/video + testo)?

2. **Presenta il piano in tabella** — Mostra un riepilogo chiaro e completo prima di eseguire:

   ```
   ## Piano Campagna

   | Parametro | Valore |
   |-----------|--------|
   | Account | [nome account] |
   | Obiettivo | Lead Generation |
   | Nome | [nome suggerito] |
   | Budget | €50/giorno |
   | Target | Donne 25-45, Italia, interesse Marketing |
   | Ottimizzazione | Lead Generation |
   | Creative | Immagine + testo + CTA |
   | Stato iniziale | In pausa (lo attivi tu quando vuoi) |

   Tutto corretto? Procedo?
   ```

3. **Aspetta conferma esplicita** — Non procedere finche' l'utente non approva
4. **Esegui e riporta** — Crea tutto e mostra i risultati:

   ```
   ## Creato con successo

   | Elemento | ID |
   |----------|----|
   | Campagna | 123456 |
   | Ad Set | 789012 |
   | Creative | 345678 |
   | Ad | 901234 |

   La campagna e' in pausa. Vuoi attivarla?
   ```

### Conferma richiesta per:
- Creazione: campagne, ad set, ads, creative, audience, lookalike
- Modifiche: budget, targeting, status, nomi
- Attivazione: `resume_campaign`
- Eliminazione: qualsiasi `delete_*`

### Conferma NON richiesta per:
- Lettura: `list_*`, `get_insights`, `get_daily_trends`, etc.
- Diagnostica: `health_check`, `validate_token`
- Export: `export_insights`

---

## Comunicazione con l'utente

- Rispondi in italiano se l'utente scrive in italiano
- Usa tabelle markdown per presentare dati, piani e risultati
- Quando mostri performance, aggiungi un breve commento interpretativo (es. "Il CTR e' sopra la media, buon segnale")
- Se un'operazione fallisce, spiega il problema in modo chiaro e suggerisci come risolverlo
- Non mostrare ID tecnici a meno che non servano — usa nomi leggibili dove possibile
- Quando l'utente chiede "come vanno le campagne", parti sempre da `list_campaigns` con status ACTIVE, poi `get_insights` sulle attive

---

## Regole critiche

### date_preset
Valori validi: `today`, `yesterday`, `last_3d`, `last_7d`, `last_14d`, `last_28d`, `last_30d`, `last_90d`, `this_month`, `last_month`, `this_quarter`, `last_quarter`, `this_week_sun_today`, `this_week_mon_today`, `last_week_sun_sat`, `last_week_mon_sun`, `this_year`, `last_year`, `maximum`.

**`lifetime` NON e' valido.** Usa `maximum` per tutti i dati storici.

### Account ID
Usa sempre il formato con prefisso `act_`: `act_123456789`.

### Budget in centesimi
`daily_budget` e `lifetime_budget` sono in centesimi. 5000 = 50.00 nella valuta dell'account. `lifetime_budget` richiede `stop_time`/`end_time`.

### Currency
Il server rileva automaticamente la valuta dell'account. NON assumere USD — la maggior parte degli account e' in EUR.

### Campagne create in PAUSED
`create_campaign` crea sempre campagne in PAUSED. Usa `resume_campaign` per attivare (dopo conferma utente).

### Gerarchia
Account -> Campaign -> Ad Set -> Ad (con Creative). Naviga sempre dall'alto verso il basso.

---

## Workflow

### Lettura (analisi account)
```
1. list_ad_accounts -> scegli account
2. list_campaigns(account_id, status="ACTIVE") -> scegli campagna
3. list_ad_sets(campaign_id=...) -> scegli ad set
4. list_ads(ad_set_id=...) -> vedi ads
5. get_insights(object_id=..., date_preset="last_30d") -> performance
```

### Creazione (lancia una nuova campagna)
```
1. FAI DOMANDE all'utente
2. PRESENTA IL PIANO in tabella
3. ASPETTA CONFERMA
4. create_campaign -> campaign_id
5. create_ad_set -> ad_set_id
6. upload_image (se serve) -> image_hash
7. create_creative -> creative_id
8. create_ad -> ad_id
9. MOSTRA RIEPILOGO con tutti gli ID creati
10. CHIEDI se attivare -> resume_campaign (solo su conferma)
```

### Analisi
- `get_insights` — performance singolo oggetto
- `compare_performance` — confronto side-by-side (serve 2+ ID)
- `get_daily_trends` — breakdown giornaliero con direzione trend
- `get_attribution_data` — finestre di attribuzione (1d_click, 7d_click, 1d_view)
- `export_insights` — export CSV/JSON

### Audience
- `list_audiences(account_id)` — audience esistenti
- `create_custom_audience` — audience website/app/customer file
- `create_lookalike` — lookalike da audience sorgente (ratio 0.01-0.20)
- `estimate_audience_size` — stima reach per targeting spec

---

## Formato targeting
```json
{
  "geo_locations": {"countries": ["IT"]},
  "age_min": 25,
  "age_max": 55,
  "genders": [1],
  "interests": [{"id": "6003139266461", "name": "Digital marketing"}]
}
```

## Obiettivi campagna
`OUTCOME_AWARENESS`, `OUTCOME_ENGAGEMENT`, `OUTCOME_LEADS`, `OUTCOME_SALES`, `OUTCOME_TRAFFIC`, `OUTCOME_APP_PROMOTION`

## response_format
Tutti i tool di lettura accettano `response_format`: `markdown` (default) o `json` (per elaborazioni successive).

## Server health
Usa `health_check` per verificare la connettivita'. Usa `validate_token` per controllare il token.

## Source code
- Server: `meta_ads_mcp/server.py`
- Tools: `meta_ads_mcp/tools/` (analytics.py, campaigns.py, ad_sets.py, ads.py, creatives.py, audiences.py, account.py, oauth.py)
- Models/enums: `meta_ads_mcp/models/common.py`
- Formatting: `meta_ads_mcp/utils/formatting.py`
- Client API: `meta_ads_mcp/client.py`
