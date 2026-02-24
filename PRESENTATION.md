# Meta Ads Manager per Claude Code

### Gestisci le campagne Meta parlando in italiano.
### Zero click. Zero Ads Manager. Solo conversazione.

---

## Il problema

Ogni advertiser lo sa:

| Attivita' | Quanto tempo perdi |
|---|---|
| Check mattutino campagne | 15-20 minuti |
| Report mensile per il cliente | 1-2 ore |
| Creare una campagna completa | 20-30 minuti |
| Confrontare campagne tra loro | 30 minuti + Excel |
| Creare una lookalike audience | 5-10 minuti |
| Mettere in pausa una campagna | 2 minuti + 5 click |

L'Ads Manager e' lento, cambia interfaccia ogni 3 mesi, e ogni operazione richiede decine di click.

**Moltiplica tutto per il numero di clienti.**

---

## La soluzione

Un **server MCP** che connette Claude direttamente alle API di Meta.

Tu scrivi in italiano. Claude esegue.

```
Tu:      "Come stanno andando le campagne questa settimana?"

Claude:  Analizza tutte le campagne attive e restituisce
         una tabella con spesa, risultati, costo per risultato
         e trend vs settimana precedente.
```

Nessun menu. Nessun filtro. Nessun export manuale.

---

## 36 strumenti. 8 categorie. Tutto l'Ads Manager.

| Categoria | Tools | Cosa fai |
|-----------|:-----:|----------|
| **Campagne** | 6 | Crea, modifica, pausa, riattiva, elimina campagne |
| **Ad Set** | 5 | Targeting, budget, posizionamenti, ottimizzazione |
| **Inserzioni** | 4 | Crea e gestisci le singole ads |
| **Analytics** | 5 | Performance, trend, confronti paralleli, export CSV/JSON |
| **Audience** | 5 | Custom audience, lookalike, stime di reach |
| **Creativita'** | 4 | Crea creativi, carica immagini, anteprima formati |
| **OAuth** | 5 | Autenticazione, token management, validazione |
| **Account** | 2 | Lista account, health check |

---

## Esempi reali

### 1. Check performance

> "Dammi un riepilogo delle campagne attive degli ultimi 7 giorni"

| Campagna | Spesa | Risultati | Costo/Risultato | Trend |
|----------|-------|-----------|-----------------|-------|
| Lead Gen Webinar | €210 | 42 lead | €5.00 | +12% |
| Retargeting Shop | €150 | 18 acquisti | €8.33 | -5% |
| Brand Awareness | €300 | 45K reach | €6.67 CPM | stabile |

**10 secondi invece di 15 minuti.**

---

### 2. Confronta campagne

> "Confronta le 3 campagne attive e dimmi quale performa meglio"

Claude analizza in **parallelo** (async) e ti dice:
- Quale ha il ROAS migliore
- Quale sta sprecando budget
- Cosa suggerisce di fare

---

### 3. Crea campagna da zero

> "Crea una campagna lead gen per il mio corso online.
> Target: donne 25-45 in Italia, interesse marketing digitale.
> Budget: 30 euro/giorno."

Claude crea in automatico:
1. Campagna (in pausa, per sicurezza)
2. Ad set con targeting esatto
3. Collega la creative
4. Ti chiede conferma prima di attivare

**Zero click nell'Ads Manager.**

---

### 4. Gestisci il budget

> "La campagna Retargeting sta andando male. Mettila in pausa
> e sposta il budget sulla Lead Gen."

Claude:
1. Mette in pausa la campagna
2. Aggiorna il budget dell'altra
3. Conferma le modifiche

---

### 5. Crea audience

> "Crea un pubblico simile ai miei migliori clienti, 2% in Italia"

Claude crea la lookalike e ti dice quante persone stimate raggiungerai.

---

### 6. Report per il cliente

> "Esportami le performance dell'ultimo mese in CSV, divise per eta' e genere"

File CSV pronto da inviare o aprire in Excel. **30 secondi.**

---

## Prima vs Dopo

| Attivita' | Prima (manuale) | Con Claude | Risparmio |
|-----------|:-:|:-:|:-:|
| Check performance mattutino | 15-20 min | 10 sec | **~99%** |
| Confronto tra campagne | 30 min | 10 sec | **~99%** |
| Creare campagna completa | 20-30 min | 1 min | **~95%** |
| Report mensile per cliente | 1-2 ore | 30 sec | **~99%** |
| Mettere in pausa campagna | 2 min | 1 frase | **~95%** |
| Creare lookalike audience | 5-10 min | 1 frase | **~95%** |

> Se gestisci anche solo 3 clienti e dedichi 1 ora/giorno all'Ads Manager:
> **risparmi ~20 ore al mese.**

---

## Sicurezza by design

- Le campagne si creano **sempre in pausa** — mai attivazioni accidentali
- **Tu dai le istruzioni, Claude esegue** — nessuna azione autonoma
- Ti chiede **conferma prima di ogni modifica** importante

---

## Per chi e' pensato

| Chi | Perche' |
|---|---|
| **Advertiser freelance** | Gestisci piu' clienti risparmiando ore ogni giorno |
| **Piccoli business** | Gestisci le ads senza dipendere da un'agenzia |
| **Team marketing** | Velocizza le operazioni quotidiane del team |
| **Agenzie** | Scala senza aggiungere persone |

---

## Cosa NON e'

- **NON e' un bot autonomo** — Tu decidi, lui esegue
- **NON attiva campagne senza permesso** — Tutto nasce in pausa
- **NON serve saper programmare** — Parli in italiano naturale
- **NON sostituisce la strategia** — Tu pensi, lui accelera l'esecuzione

---

## Auto-documentazione: `.claude/CLAUDE.md`

Il server include un file `.claude/CLAUDE.md` che **insegna a Claude Code come usare l'MCP correttamente**, senza errori.

Cosa contiene:

| Sezione | Cosa insegna a Claude |
|---------|----------------------|
| **Regole critiche** | Valori validi per `date_preset`, formato account ID, budget in centesimi |
| **Currency auto-detect** | Il server rileva la valuta dell'account (EUR, USD, GBP...) e mostra il simbolo corretto |
| **Workflow patterns** | Sequenze corrette per leggere dati, creare campagne, analizzare performance |
| **Gerarchia** | Account -> Campaign -> Ad Set -> Ad — navigazione top-down |
| **Targeting spec** | Formato JSON esatto per targeting, interessi, geo |
| **Source code map** | Dove trovare ogni file per modifiche future |

Esempio di regola critica:

```
date_preset "lifetime" NON e' valido per Meta API.
Usa "maximum" per ottenere tutti i dati storici.
```

> Claude legge questo file automaticamente e **non commette errori** gia' noti.

---

## Currency dinamica

Il server rileva automaticamente la **valuta dell'account** dalle API di Meta e mostra il simbolo corretto.

| Account | Currency | Output |
|---------|:--------:|--------|
| ROIX10 LTD | EUR | €188.94 |
| US Client | USD | $1,250.00 |
| UK Agency | GBP | £430.50 |

Niente piu' `$` su account europei. Il simbolo si adatta all'account.

Valute supportate: USD ($), EUR (€), GBP (£), JPY (¥), CHF, CAD (CA$), AUD (A$), BRL (R$), INR (₹) e tutte le altre (fallback sul codice ISO).

---

## I numeri

| | |
|:---|:---|
| **36** | Strumenti MCP disponibili |
| **8** | Categorie coperte |
| **9/10** | Test superati al primo audit |
| **2** | Bug fix post-audit (lifetime preset + currency) |
| **20+ ore/mese** | Tempo risparmiato (stima conservativa) |

---

## Bug fix dal primo audit

| Bug | Problema | Fix |
|-----|----------|-----|
| `date_preset: lifetime` | Meta API non supporta `lifetime`, restituisce errore 100 | Rimosso dall'enum, documentato `maximum` come alternativa |
| Currency hardcoded `$` | Tutti gli importi mostravano `$` anche su account EUR | Il server ora legge `account_currency` dall'API e usa il simbolo corretto |

Entrambi i fix sono coperti dalla documentazione in `.claude/CLAUDE.md` per evitare regressioni future.

---

## La domanda giusta

Non e': *"Quanto costa?"*

E': **"Quante ore risparmio ogni settimana?"**

> Se passi anche solo 1 ora al giorno nell'Ads Manager,
> con questo strumento ne risparmi almeno la meta'.
>
> **5 ore a settimana. 20 ore al mese.**
>
> Tempo che puoi dedicare a strategia, creativita' e clienti.

---

## Licenza

Questo software e' rilasciato con **licenza per uso personale**.

- Uso personale e professionale del licenziatario
- **Vietata** la distribuzione a terzi
- **Vietata** la rivendita, anche parziale
- **Vietata** la sublicenza
- **Vietata** la modifica e redistribuzione

© 2026 Matteo Milone. Tutti i diritti riservati.

---

*Built for Scalers+ community di Matteo Milone
