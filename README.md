# Sommer-konkurrence: Strava-klubber

Automatisk, gratis "app" (en webside du lægger på din telefons hjemmeskærm),
der viser hvilken klub der har løbet flest km siden 1. juli, samt en rangeret
liste over medlemmer.

## Sådan virker det

- `fetch_and_update.py` henter aktiviteter fra begge klubber, sammenligner
  med jeres "før juli"-filer og med alt vi allerede har set før, og gemmer
  kun det NYE.
- GitHub Actions (`.github/workflows/update.yml`) kører scriptet automatisk
  hver 3. time, helt gratis.
- `docs/index.html` er selve siden, der viser resultatet. GitHub Pages
  hoster den gratis.

## Trin 1: Læg jeres "før juli"-filer ind

Omdøb jeres to eksisterende JSON-filer og læg dem her:

```
data/baseline_klub1.json
data/baseline_klub2.json
```

**Vigtigt forbehold:** jeres oprindelige script overskrev filen i hvert
loop (`json.dump(response_data, f...)` inde i while-loopet), så den fil I
sad tilbage med, indeholder kun den SIDSTE side der blev hentet — ikke alle
aktiviteter. Det betyder at "før juli"-filen sandsynligvis mangler nogle
aktiviteter. Konsekvensen er at et lille antal ret gamle løbeture i teorien
kunne dukke op som "nye" i starten. I praksis forsvinder gamle aktiviteter
hurtigt ud af Stravas klub-feed (som kun viser de ca. 200 seneste), så
risikoen er lille — men hold øje med resultat-listen den første uge, og
slet evt. en åbenlyst forkert linje direkte i `data/activities_store.json`,
hvis I ser noget der tydeligvis er en gammel aktivitet.

## Trin 2: Opret GitHub-repo

1. Gå til github.com og opret et nyt, **privat** repository (fx `sommer-konkurrence`).
2. Upload alle filerne i denne mappe til repoet (drag-and-drop virker fint
   på github.com, eller brug git fra din computer).

## Trin 3: Sæt hemmeligheder op (Secrets)

Gå til repoet → **Settings → Secrets and variables → Actions → Secrets** og
opret disse fire:

| Navn | Værdi |
|---|---|
| `STRAVA_CLIENT_ID` | jeres client_id |
| `STRAVA_CLIENT_SECRET` | jeres client_secret |
| `STRAVA_REFRESH_TOKEN_1` | refresh_token til klub 1 |
| `STRAVA_REFRESH_TOKEN_2` | refresh_token til klub 2 (samme som ovenstående, hvis det er samme Strava-bruger der er medlem af begge klubber) |

## Trin 4: Sæt variabler op (Variables)

Samme sted, men fanen **Variables**, opret:

| Navn | Værdi |
|---|---|
| `KLUB1_ID` | `2180428` (jeres klub-id) |
| `KLUB1_NAVN` | fx `Løbeklub Nord` |
| `KLUB2_ID` | klub 2's id |
| `KLUB2_NAVN` | fx `Løbeklub Syd` |

## Trin 5: Slå GitHub Pages til

**Settings → Pages** → under "Build and deployment": vælg
**Deploy from a branch**, branch `main`, mappe `/docs`. Gem. Efter ca. et
minut får I en URL i stil med:

```
https://dit-brugernavn.github.io/sommer-konkurrence/
```

## Trin 6: Test det manuelt

Gå til fanen **Actions** → workflowet "Opdater Strava-konkurrence" →
**Run workflow**. Vent et minut, tjek at den blev grøn, og besøg jeres
Pages-URL — der skulle nu ligge tal.

## Trin 7: Læg den som "app" på telefonen

Åbn Pages-URL'en i Safari (iPhone) eller Chrome (Android) →
**Del → Føj til hjemmeskærm**. Nu ligger den som et app-ikon og åbner
i fuld skærm uden browser-bjælke.

## Løbende drift

Herefter kører det helt af sig selv hver 3. time, uden I skal gøre noget.
Vil I have hyppigere opdateringer, kan I ændre cron-linjen i
`.github/workflows/update.yml` (fx `0 */1 * * *` for hver time — men gå
ikke under det, for at holde jer inden for Stravas rate-limits).

Hvis Strava på et tidspunkt afviser refresh-tokenet (sker sjældent, men kan
ske hvis I fjerner appens adgang på strava.com), skal I bare generere et nyt
og opdatere secret'en.
