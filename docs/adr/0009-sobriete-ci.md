# 0009 — CI sobre : déclencheurs restreints, jobs regroupés, matrice du template ciblée

- Statut : Acceptée
- Date : 2026-10-07

## Contexte

Le quota GitHub Actions du compte (3 000 minutes Linux par mois, repos
privés) a été épuisé en quatre jours de migration, du 1er au 6 octobre 2026.
Le relevé job par job (facturation reconstituée à 1 % près) donne :

- 56 % pour la matrice du template (18 combinaisons langage × base × auth,
  50 à 85 minutes par passage), dont 23 % rejoués sur `main` après chaque
  merge pour écrire les caches, docs comprises ;
- 18 % de CI complètes relancées sans nouveau code : `ci.yml` écoutait
  `edited`, `labeled` et `unlabeled`, dont pr-checks a besoin mais pas la CI
  lourde (jusqu'à 11 runs à la même seconde quand des labels sont posés un
  par un) ;
- 31 % d'arrondi : GitHub facture chaque job à la minute entamée, et 860
  jobs sur 1 575 duraient moins d'une minute (agrégateurs de 3 s, `just
  check` et build de l'image dans des jobs séparés, 4 jobs de 15 s dans Oikos).

Un runner auto-hébergé n'y change rien tant que la charge reste la même :
la pointe atteignait 253 minutes de calcul en une heure, soit au moins cinq
runners pour ne pas accumuler de retard.

## Décision

1. **pr-checks dans son propre workflow.** Seul `pr-checks.yml` écoute
   `edited`, `labeled`, `unlabeled` (et `ready_for_review`). `ci.yml` ne
   réagit qu'à du code nouveau : `opened`, `synchronize`, `reopened`,
   `ready_for_review`. Le nom du check requis (`pr-checks / checks`) ne
   change pas.
2. **Pas de CI lourde sur un brouillon.** Le job `ci` est sauté tant que la
   PR est en brouillon ; on valide en local (`just check`). Le passage en
   *Ready for review* lance la CI. Un brouillon ne peut pas être mergé, et
   `ci / check` absent bloque de toute façon le merge.
3. **Un job par contrôle.** `ci-python`, `ci-go`, `ci-rust` enchaînent
   `just check` et le build de l'image dans un seul job `check` (le check
   requis garde son nom `ci / check`). Plus de job agrégateur.
4. **Pas de re-validation de `main` après merge** quand la PR vient d'être
   testée ; `main` est revalidé par la release (build de l'image).
5. **Matrice du template ciblée** (`lduf/ktisis`) : une PR ne teste que les
   langages qu'elle touche, sur une combinaison par langage, et les six
   combinaisons d'un langage quand le diff touche `with_db` ou `auth_mode`.
   Les 18 combinaisons tournent chaque nuit si `main` a bougé, sur label
   `ci:full`, ou à la main. Un job par langage enchaîne ses combinaisons sur
   le même runner, caches chauds.
6. **Mises à jour du template groupées** : `template-update` ouvre les PR
   `copier update` des apps le lundi (ou à la main), plus après chaque
   release du template.
7. **Concurrence** : un nouveau commit sur une PR annule la CI en cours de
   cette PR ; jamais la release.

## Conséquences

- Rejouée sur les jobs d'octobre, la facture passe de 3 020 à environ 580
  minutes (−81 %), la pointe horaire de 253 à 57 minutes de calcul : un
  seul runner auto-hébergé suffirait.
- Retour de CI plus tardif pour un agent qui travaille en brouillon : il doit
  lancer `just check` lui-même avant de pousser.
- Une régression propre à une combinaison non testée en PR (ex. `proxy` sans
  base) peut atteindre `main` ; la matrice de la nuit la signale par e-mail
  (échec de workflow planifié), et le label `ci:full` existe pour une PR à
  risque.
- La PR et l'image de la release sont construites séparément : la version est
  inscrite dans l'image au build (contrat d'app), une image de PR ne peut pas
  être promue telle quelle.

## Alternatives écartées

- **Garde `if: github.event.action != 'edited'` dans un seul workflow** : un
  job sauté compte comme un succès pour le check requis et peut masquer un
  échec précédent sur le même commit.
- **Cache Docker en registre (GHCR)** : sort du plafond de 10 Go du cache
  Actions, mais le stockage des paquets privés est limité à 2 Go sur le plan
  Pro ; on réduit plutôt les scopes de cache (un par langage).
- **Runner auto-hébergé d'abord** : file d'attente sans fin à charge égale ;
  il vient après ces optimisations.
- **Rendre `lduf/ktisis` public** (minutes gratuites) : décision de
  visibilité du code, laissée à part.
