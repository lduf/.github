# 0002 — just comme interface de commandes commune

- Statut : Acceptée
- Date : 2026-10-01

## Contexte

Chaque langage a ses commandes (`uv run pytest`, `go test ./...`,
`cargo nextest run`…). Un humain, la CI et un agent LLM doivent aujourd'hui
connaître le langage d'un projet pour savoir comment le vérifier. Les
workflows CI dupliquent aussi cette connaissance.

## Décision

Chaque app générée contient un `justfile` avec des **recettes de même nom et de
même sémantique**, quel que soit le langage :

| Recette | Rôle |
|---|---|
| `just dev` | Lance l'app en local avec rechargement (via `compose.dev.yml` si `with_db`) |
| `just check` | Format (vérification), lint, types, tests. **C'est la porte de qualité** : la CI exécute exactement cette recette |
| `just test` | Tests seuls |
| `just fmt` | Formate le code (écriture) |
| `just build` | Construit l'image Docker |
| `just run` | Lance l'image construite, comme en prod |

- Une app **PEUT** ajouter des recettes propres. Elle **NE DOIT PAS** changer la
  sémantique des six recettes ci-dessus.
- Les workflows réutilisables `ci-*.yml` appellent `just check` et `just build`
  au lieu de réécrire les commandes.

## Conséquences

- Une seule commande à connaître pour vérifier n'importe quel projet. La
  définition de « vert » est identique en local et en CI.
- `just` devient un outil requis en local et en CI (action
  `extractions/setup-just`).
- Les recettes sont templatées par Copier selon `lang` et `with_db`.

## Alternatives écartées

- **Makefile** : syntaxe et pièges (tabulations, `.PHONY`, variables) peu
  adaptés à un simple lanceur de commandes, et comportement variable selon
  l'OS.
- **Scripts propres à chaque langage** (`pyproject` scripts, `mage`,
  `cargo xtask`) : ils ne donnent pas une interface commune.
