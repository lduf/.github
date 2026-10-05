# Contrat d'app — `contract: v1`

Référence commune de toutes les apps générées depuis `lduf/ktisis`,
quel que soit leur langage (Python, Go, Rust). Oikos (déploiement GitOps) et
Iaso (tri des erreurs depuis Loki) s'appuient sur ce contrat : une app qui le
respecte se déploie, se supervise et se diagnostique sans configuration
spécifique.

- Les mots **DOIT**, **NE DOIT PAS**, **DEVRAIT** et **PEUT** ont le sens de la
  [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).
- Le contrat est versionné (`v1`). Une app générée par le template indique la
  version qu'elle respecte dans son `README.md` ; la version du template
  (`_commit` dans `.copier-answers.yml`) détermine celle du contrat. Tout
  changement incompatible du contrat fait passer en `v2` et passe par une ADR.
- Décisions associées : [ADR 0006](adr/0006-contrat-app-commun.md).

## 1. Endpoints HTTP

Port applicatif : **8080** (`SERVER__PORT`). Les réponses sont en JSON.

| Route | Rôle | Contrat |
|---|---|---|
| `GET /healthz` | Liveness : le processus répond | **DOIT** répondre `200 {"status":"ok"}` sans aucune I/O (ni DB, ni réseau). |
| `GET /readyz` | Readiness : les dépendances répondent | `200 {"status":"ok","checks":{...}}` si toutes les dépendances répondent, sinon `503` avec le détail par dépendance (`{"db":"ok"}` / `{"db":"error"}`). Sans dépendance : toujours `200`, `checks` vide. **DOIT** passer en `503` dès la réception de SIGTERM (§6). Timeout par check ≤ 2 s. |
| `GET /api/version` | Version déployée | `{"version":"1.4.2","commit":"<sha court>","build_date":"<RFC 3339>"}`. Valeurs injectées au build (§7). |
| `GET /api/me` | Utilisateur courant | Selon `auth_mode`, voir §1.1. |
| `/auth/*` | Flux OIDC | Selon `auth_mode`, voir §1.1. |

`/healthz` et `/readyz` sont **exclus** de l'access log et des métriques HTTP
(§2, §3) : ils sont appelés en boucle et ne portent aucune information métier.

Les messages d'erreur JSON suivent la forme `{"error":"<code_court>","detail":"<texte>"}`.
Ils ne contiennent jamais de stack trace ni de secret.

### 1.1 Authentification selon `auth_mode`

Valeur choisie à la génération (question Copier `auth_mode`). Il n'y a jamais
d'auth maison (pas de table d'utilisateurs ni de mots de passe).

| | `oidc` | `proxy` | `public` |
|---|---|---|---|
| Qui authentifie | L'app, en OIDC Authorization Code (+ PKCE) auprès d'Authentik | Traefik + l'outpost Authentik (forward-auth) | Personne |
| `/auth/login`, `/auth/callback`, `/auth/logout` | Présents | **Absents (404)** | **Absents (404)** |
| `GET /api/me` | `200` avec l'utilisateur de la session, `401` sinon | `200` avec l'utilisateur lu dans les en-têtes, `401` s'ils sont absents | **Absent (404)** |
| Config | `OIDC__*` | `PROXY__TRUSTED_NETWORKS` | — |

Forme de `/api/me` (identique en `oidc` et en `proxy`) :

```json
{"sub": "a1b2c3", "username": "lucas", "groups": ["admins"]}
```

- `sub` est l'identifiant stable : c'est lui qu'on utilise dans les logs (§3),
  jamais l'email.
- **Mode `proxy`** : `sub` ← `X-authentik-uid`, `username` ← `X-authentik-username`,
  `groups` ← `X-authentik-groups` (séparateur `|`). Ces en-têtes **NE DOIVENT**
  être acceptés que si la requête vient d'une adresse de
  `PROXY__TRUSTED_NETWORKS` (défaut : sous-réseau du réseau Docker `proxy`).
  Sinon l'app les ignore et répond `401`. Le conteneur n'expose aucun port sur
  l'hôte.
- **Mode `oidc`** : `OIDC__ENABLED=false` active un utilisateur factice pour le
  dev local. Ce mode **NE DOIT JAMAIS** être déployé : l'app logge un
  `warn` `oidc_disabled` au démarrage.

## 2. Métriques Prometheus

- Listener **séparé** sur le port **9300** (`METRICS__PORT`), chemin `/metrics`,
  format texte Prometheus. Ce port **NE DOIT PAS** être routé par Traefik : il
  n'est joignable que depuis le réseau `prometheus_net`.
- Noms et labels **communs à toutes les apps**, pour que le dashboard générique
  fonctionne sans adaptation :

| Métrique | Type | Labels |
|---|---|---|
| `http_requests_total` | counter | `route`, `method`, `status` |
| `http_request_duration_seconds` | histogram | `route`, `method`, `status` |
| `<app>_build_info` | gauge (valeur `1`) | `version`, `commit` |

Règles :

- `route` est le **modèle** de route déclaré (`/api/items/{id}`), jamais le
  chemin brut, pour que la cardinalité reste bornée. Une requête qui ne
  correspond à aucune route a `route="unmatched"`.
- `status` est le code HTTP exact sous forme de chaîne (`"200"`, `"503"`), pas
  une classe `2xx`.
- `method` est en majuscules (`GET`).
- `<app>` est `app_name` en snake_case (`mon-app` → `mon_app_build_info`).
- Buckets de l'histogramme (en secondes, identiques dans les 3 langages) :
  `0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10`.
- `/healthz`, `/readyz` et `/metrics` ne sont pas comptés.
- Les métriques du runtime (`process_*`, `go_*`, `python_*`) **PEUVENT** être
  exposées. Les métriques métier **DEVRAIENT** être préfixées par `<app>_`.
- Une app **générée par Ktisis** (`lduf/ktisis`) expose en plus
  `ktisis_info` (gauge, valeur `1`), labels `template_version` (le `_commit`
  de son `.copier-answers.yml`, ex. `v0.9.0`), `contract` (`v1`), `lang`,
  `auth` et `db` (`true`/`false`). Écrite par Copier, mise à jour par
  `copier update` ; elle sert au suivi d'adoption et de retard de template.
  Une app hors Ktisis **NE DOIT PAS** l'exposer (`ktisis check` la signale
  sans échouer).

## 3. Logs

Une ligne JSON par événement, sur **stdout uniquement** (jamais de fichier).
Promtail/Alloy les envoie dans Loki, où Iaso les lit.

### 3.1 Schéma

| Clé | Obligatoire | Contenu |
|---|---|---|
| `ts` | oui | Horodatage RFC 3339 en UTC, à la milliseconde : `2026-10-01T12:00:00.123Z` |
| `level` | oui | `debug` \| `info` \| `warn` \| `error` (minuscules, ces quatre valeurs uniquement) |
| `msg` | oui | **Nom d'événement** court en snake_case (`user_created`), pas une phrase interpolée |
| `service` | oui | `app_name` |
| `version` | oui | Version déployée (comme `/api/version`) |
| `request_id` | dans le contexte d'une requête | Valeur de `X-Request-Id`, reçue ou générée (UUID v4), renvoyée dans la réponse |
| `error` | sur une erreur | Objet `{"type": "...", "message": "...", "stack": "..."}` |
| *(autres)* | non | Champs métier **à plat** (`user_id`, `item_id`, `duration_ms`) |

Exemple :

```json
{"ts":"2026-10-01T12:00:00.123Z","level":"error","msg":"payment_failed","service":"mon-app","version":"1.4.2","request_id":"6f1c…","order_id":42,"error":{"type":"TimeoutError","message":"upstream timed out","stack":"Traceback …"}}
```

Côté Loki, `| json` aplatit l'objet en `error_type`, `error_message`,
`error_stack`. Requête typique pour Iaso :

```logql
{service="mon-app"} | json | level="error" | line_format "{{.error_type}}: {{.error_message}}"
```

### 3.2 Règles

- **Aucun log en texte brut**, y compris ceux des librairies tierces (uvicorn,
  SQLAlchemy, `net/http`, hyper…) : ils sont redirigés vers le même formateur.
- `DEBUG=true` (dev local uniquement) **PEUT** passer à un rendu console
  lisible. En prod, toujours du JSON.
- Le niveau est piloté par `LOG_LEVEL` (`debug|info|warn|error`, défaut `info`).
  `WARNING` est accepté comme alias de `warn`.
- **Access log** automatique, émis par le middleware, une ligne par requête :
  `msg="http_request"`, `method`, `route`, `path`, `status`, `duration_ms`,
  `request_id`. Sans query string ni body.
- **Jamais** de secret (token, mot de passe, cookie, en-tête `Authorization`)
  ni de PII (email, nom) : les utilisateurs sont identifiés par `sub`.
- **Une erreur = un log**, émis là où elle est gérée, avec `error.stack`. Pas de
  log suivi d'un re-raise en cascade.
- Niveaux : `debug` pour le diagnostic local ; `info` pour les événements métier
  et les accès ; `warn` pour une anomalie récupérable ; `error` pour une
  fonctionnalité en échec. Pas de log dans les boucles chaudes.

## 4. Configuration

- Uniquement par **variables d'environnement**, avec le délimiteur `__` pour
  les sections : `SECTION__CLE` (`OIDC__CLIENT_SECRET`). Les clés globales
  n'ont pas de section (`APP_NAME`, `LOG_LEVEL`).
- Toute la config passe par la structure typée du starter (`Settings`, `Config`).
  Pas d'accès sauvage à l'environnement dispersé dans le code. La config est
  validée au démarrage : une valeur invalide arrête l'app immédiatement, avec
  un log `error` `config_invalid` qui ne contient pas la valeur.
- **Secrets** : fournis uniquement par l'environnement (Portainer aujourd'hui,
  Oikos demain), jamais committés. Ils sont typés secret (`SecretStr`, `Secret`,
  `SecretString`) et masqués dans les logs, les `repr` et les erreurs.
- Les variables d'environnement font partie de l'API de déploiement : en
  supprimer ou en renommer une est un changement cassant (voir
  [ADR 0003](adr/0003-commitizen-semver-conventional-commits.md)).

Variables communes :

| Variable | Défaut | Rôle |
|---|---|---|
| `APP_NAME` | `app_name` du template | Valeur de `service` dans les logs |
| `LOG_LEVEL` | `info` | Niveau de log |
| `DEBUG` | `false` | Rendu console lisible (dev uniquement) |
| `SERVER__PORT` | `8080` | Port HTTP applicatif |
| `SERVER__SHUTDOWN_TIMEOUT` | `10` | Délai de grâce à l'arrêt, en secondes (§6) |
| `METRICS__PORT` | `9300` | Port du listener `/metrics` |
| `SESSION_SECRET` | — (requis en `oidc`) | Signature du cookie de session |
| `OIDC__ENABLED`, `OIDC__ISSUER`, `OIDC__CLIENT_ID`, `OIDC__CLIENT_SECRET`, `OIDC__SCOPES` | — | `auth_mode=oidc` uniquement |
| `PROXY__TRUSTED_NETWORKS` | sous-réseau `proxy` | `auth_mode=proxy` uniquement (CIDR séparés par des virgules) |
| `DATABASE__HOST`, `DATABASE__PORT`, `DATABASE__NAME`, `DATABASE__USERNAME`, `DATABASE__PASSWORD` | — | `with_db=true` uniquement |

## 5. Healthcheck

- L'exécutable de l'app **DOIT** fournir une sous-commande `healthcheck`. Elle
  interroge `http://127.0.0.1:${SERVER__PORT}/healthz` et sort avec `0` si la
  réponse est `200`, `1` sinon (timeout 2 s).
- Elle fonctionne dans l'image finale, sans `curl` ni shell (distroless).
- Compose :

```yaml
healthcheck:
  test: ["CMD", "/app/<binaire>", "healthcheck"]   # Python : ["CMD", "app", "healthcheck"]
  interval: 30s
  timeout: 3s
  retries: 3
  start_period: 10s
```

## 6. Arrêt propre

À la réception de **SIGTERM** (ou SIGINT) :

1. `/readyz` passe immédiatement en `503`, et l'app logge `info` `shutdown_started`.
2. L'app arrête d'accepter de nouvelles connexions et laisse les requêtes en
   cours se terminer, dans la limite de `SERVER__SHUTDOWN_TIMEOUT` (défaut 10 s).
3. Elle ferme les ressources (pool DB), logge `shutdown_complete` et sort en `0`.
   Si le délai est dépassé, elle logge `warn` `shutdown_timeout` et sort quand même.

Aucune requête en cours n'est coupée net tant que le délai de grâce n'est pas
écoulé. `stop_grace_period` dans compose **DOIT** être supérieur au délai de
l'app (défaut : `15s`).

## 7. Image

- Build **multi-stage**, image finale exécutée en **utilisateur non-root**, sans
  outil de build.

| Langage | Image finale | Notes |
|---|---|---|
| Go | `gcr.io/distroless/static-debian12:nonroot` | `CGO_ENABLED=0`, version injectée par `-ldflags "-X main.version=… -X main.commit=…"` |
| Rust | `gcr.io/distroless/cc-debian12:nonroot` | Cache des dépendances avec cargo-chef |
| Python | `python:3.x-slim` | Venv construit par uv dans l'étape de build, puis copié ; version lue par `importlib.metadata.version()` |

- Arguments de build `VERSION`, `COMMIT` et `BUILD_DATE`, exposés par
  `/api/version` et par les labels OCI `org.opencontainers.image.version`,
  `org.opencontainers.image.revision`, `org.opencontainers.image.created` et
  `org.opencontainers.image.source`.
- Images publiées sur GHCR **uniquement lors d'une release**, avec les tags
  `X.Y.Z`, `X.Y` et `sha-<court>`. Pendant la transition Portainer, la release
  pousse aussi `latest`. Voir [ADR 0004](adr/0004-release-push-direct-sur-main.md).

## 8. Fichiers compose

| Fichier | Rôle |
|---|---|
| `compose.dev.yml` | Développement local (`just dev`) : build local, ports publiés, DB de dev si `with_db` |
| `compose.yml` | Prod, **transitoire** : déployé par Portainer aujourd'hui. Il sert de modèle à la stack Oikos, puis sort du repo de l'app une fois la migration faite |

Conventions de `compose.yml` (conventions Oikos) :

```yaml
services:
  app:
    image: ghcr.io/lduf/<app>:<X.Y.Z>
    mem_limit: 256m                 # OBLIGATOIRE sur chaque service
    stop_grace_period: 15s
    networks: [proxy, prometheus_net]
    labels:
      - traefik.enable=true
      - traefik.http.services.<app>.loadbalancer.server.port=8080
      - prometheus.scrape=true
      - prometheus.port=9300
      - prometheus.job=<app>
networks:
  proxy: { external: true }
  prometheus_net: { external: true }
```

- `mem_limit` sur **chaque** service : le serveur a peu de RAM.
- La DB, si `with_db`, est sur un réseau interne dédié. Elle n'est ni sur
  `proxy` ni sur `prometheus_net`.

## 9. Observabilité livrée par l'app

Dossier `observability/` à la racine du repo de l'app, copié par Oikos lors
du déploiement :

- `observability/dashboard.json` : dashboard Grafana **spécifique** à l'app
  (métriques métier). Les vues HTTP génériques sont dans le dashboard commun
  ([`observability/app-generic-dashboard.json`](../observability/app-generic-dashboard.json),
  variable `$app`), qu'il ne faut pas dupliquer.
- `observability/alerts.yml` : règles d'alerte au format Prometheus
  (`groups:`). Le minimum généré par le template :
  - `<App>Down` : `up{job="<app>"} == 0` pendant 2 min ;
  - `<App>High5xxRate` : la part de `status=~"5.."` dans
    `http_requests_total{job="<app>"}` dépasse 5 % sur 5 min ;
  - `<App>HighLatency` : le p95 de `http_request_duration_seconds` dépasse 1 s
    sur 10 min.

## 10. Implémentation par langage (librairies de référence)

Pour information : le contrat porte sur le comportement observable, pas sur
les librairies. Les starters utilisent :

| | Python | Go | Rust |
|---|---|---|---|
| HTTP | FastAPI + uvicorn | `net/http` (routage par motifs, Go ≥ 1.22) | axum + tower-http |
| Config | pydantic-settings | caarlos0/env | figment (provider `Env` avec `split("__")`) |
| Logs | structlog + `ProcessorFormatter` (pont stdlib) | `log/slog` (handler JSON) | tracing + tracing-subscriber (JSON) |
| Métriques | prometheus-client | client_golang | metrics + metrics-exporter-prometheus |
| OIDC | authlib | coreos/go-oidc + x/oauth2 | openidconnect |
| DB | SQLAlchemy 2 + Alembic | pgx + goose | sqlx + `sqlx migrate` |
| Qualité | uv, ruff, mypy, pytest | gofmt, go vet, golangci-lint, go test | rustfmt, clippy `-D warnings`, cargo-deny, nextest |

Toutes les apps exposent la même interface de commandes `just`
([ADR 0002](adr/0002-just-interface-commune.md)).
