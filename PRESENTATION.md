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

## Prompt da copiare e usare

### Performance e analisi

```
Dammi un riepilogo delle campagne attive degli ultimi 7 giorni
```

```
Confronta le campagne attive e dimmi quale performa meglio
```

```
Mostrami il trend giornaliero della campagna [nome] nell'ultimo mese
```

```
Qual e' il costo per lead delle campagne attive questo mese?
```

```
Quali campagne hanno speso di piu' nell'ultima settimana senza risultati?
```

### Creazione campagne

```
Crea una campagna lead gen per il mio corso online.
Target: donne 25-45 in Italia, interesse marketing digitale.
Budget: 30 euro/giorno.
```

```
Crea una campagna traffico al sito per il mio e-commerce.
Target: uomini e donne 18-35, Italia, interesse moda.
Budget: 20 euro/giorno.
```

```
Duplica la struttura della campagna [nome] ma con target diverso:
uomini 30-50 in Germania, interesse tecnologia.
```

### Gestione e ottimizzazione

```
Metti in pausa la campagna [nome] e sposta il budget sulla campagna [nome]
```

```
Aumenta il budget della campagna [nome] a 50 euro/giorno
```

```
Metti in pausa tutti gli ad set con costo per lead sopra i 10 euro
```

### Audience

```
Crea un pubblico simile ai miei migliori clienti, 2% in Italia
```

```
Quante persone posso raggiungere con target donne 25-40, Milano, interesse fitness?
```

```
Mostrami tutte le audience dell'account [nome]
```

### Report e export

```
Esportami le performance dell'ultimo mese in CSV, divise per eta' e genere
```

```
Generami un report mensile per il cliente con spesa, risultati e costo per risultato
```

```
Confronta le performance di questo mese vs mese scorso
```

---

## Come funziona: il workflow pianifica-conferma-esegui

Quando chiedi di creare o modificare qualcosa, Claude segue sempre questo processo:

**1. Ti fa domande** se mancano informazioni

**2. Ti presenta il piano in tabella:**

| Parametro | Valore |
|-----------|--------|
| Account | [selezionato] |
| Obiettivo | Lead Generation |
| Budget | €30/giorno |
| Target | Donne 25-45, Italia, interesse Marketing |
| Stato iniziale | In pausa |

*Tutto corretto? Procedo?*

**3. Aspetta la tua conferma** prima di toccare qualsiasi cosa

**4. Esegue e ti mostra il risultato** con tutti gli ID creati

> **Mai sorprese. Mai attivazioni accidentali. Sempre tu al comando.**

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
- Claude **pianifica e mostra il piano** prima di eseguire qualsiasi operazione

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

## Auto-documentazione: `CLAUDE.md`

Il server include un file `CLAUDE.md` che **insegna a Claude Code come usare l'MCP correttamente**, senza errori.

| Sezione | Cosa insegna a Claude |
|---------|----------------------|
| **Regole critiche** | Valori validi per `date_preset`, formato account ID, budget in centesimi |
| **Currency auto-detect** | Rileva la valuta dell'account e mostra il simbolo corretto |
| **Workflow pianifica-conferma-esegui** | Fa domande, presenta il piano, aspetta conferma, esegue |
| **Gerarchia** | Account -> Campaign -> Ad Set -> Ad — navigazione top-down |
| **Targeting spec** | Formato JSON esatto per targeting, interessi, geo |

> Claude legge questo file automaticamente e **non commette errori** gia' noti.

---

## Currency dinamica

Il server rileva automaticamente la **valuta dell'account** dalle API di Meta e mostra il simbolo corretto.

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
