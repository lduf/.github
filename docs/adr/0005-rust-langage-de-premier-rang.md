# 0005 — Rust, langage de premier rang à côté de Python et Go

- Statut : Acceptée
- Date : 2026-10-01

## Contexte

Jusqu'ici, Rust n'était qu'une option « pour l'extrême » : il n'avait pas de
starter, et la skill `kickstart` suggérait de copier la structure Go. En
pratique, une partie des apps prévues ont une logique métier dense, où la
justesse compte plus que la vitesse d'itération. Le serveur a aussi peu de RAM.

## Décision

Rust devient un **starter à part entière** du template Copier (`lang=rust`),
au même niveau que Python et Go : même contrat
([ADR 0006](0006-contrat-app-commun.md)), mêmes recettes `just`, même CI.

Grille de choix utilisée par `kickstart` (le choix est argumenté, jamais un
défaut) :

| Langage | Quand le choisir |
|---|---|
| **Python** | Data/IA, ORM riche, besoin d'itérer vite sur le produit, écosystème de librairies déterminant |
| **Go** | Services simples, glue, middlewares, workers ; quand le temps de build et la simplicité comptent |
| **Rust** | Logique métier dense, exigence de justesse (le système de types porte les invariants), traitement CPU, mémoire maîtrisée au plus juste |

Stack Rust : axum + tower-http, figment, tracing + tracing-subscriber (JSON),
metrics + metrics-exporter-prometheus, openidconnect, sqlx. Qualité : rustfmt,
clippy `-D warnings`, cargo-deny, nextest. Image `distroless/cc` avec
cargo-chef.

## Conséquences

- Trois starters à maintenir en parité : la CI matrice du template et le
  contrat sont ce qui empêche la dérive.
- Les builds Rust sont plus longs : cargo-chef et le cache de CI sont
  obligatoires pour tenir l'objectif « projet vert en moins de 5 minutes ».
- L'empreinte RAM d'une app Rust est comparable à Go, et bien inférieure à
  Python.

## Alternatives écartées

- **Rust réservé aux cas extrêmes** : sous-utilisé alors qu'il convient à une
  partie des besoins réels, et sans starter le premier projet Rust aurait été
  improvisé.
- **Seulement deux langages (Python + Go)** : on perd la garantie de justesse
  pour les domaines denses.
