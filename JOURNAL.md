# JOURNAL

## 2026-06-24 — chore(rename): protest devient apte

Nom `protest` pris sur PyPI (projet dormant, demande PEP 541 en attente). Nom
libre trouve : `apte`. Rename complet du projet.

Avant le rename, merge de tout ce qui etait ouvert pour eviter les conflits :
7 PRs squash-merge (#129 #130 #131 #133 #134 fix evals/di, #128 #132 dependabot).
La release-please #121 laissee ouverte, elle se regenerera en release `apte`.

Rename : `git mv protest apte`, puis remplacement `ProTest`->`Apte` (brand, dont
les classes `ProTestSession`/`ProTestSuite`) et `protest`->`apte` (package, imports,
CLI, URLs github, dossier runtime `.protest/`->`.apte/`) sur 208 fichiers tracks.

Deux pieges rencontres :
- gitignore renomme `.protest/`->`.apte/` : l'ancien dossier runtime n'etait plus
  ignore, `git add -A` a voulu committer 545 fichiers d'artefacts. Supprimes du disque.
- `uv sync`/`uv lock` re-resolvent et bumpent des deps non liees (mypy 1.20->2.1).
  Refuse : uv.lock garde le lock de main avec juste le nom du package change.

Valide : 1264 tests passent, lint clean, CLI `apte --help` ok.

Reste : renommer le repo GitHub `renaudcepre/protest`->`apte` (+ remote), et mettre
a jour `publish.yml` (le commentaire PARKED part, le nom est libre) et le post reddit.
