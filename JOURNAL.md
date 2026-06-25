# JOURNAL

## 2026-06-25 — fix(interrupt): soft-stop flaky sous 3.14 apres le fix event-bus

CI rouge sur la PR #144 (handlers sync inline) : un seul test casse,
`test_soft_stop_prevents_pending_tests_from_starting`, et seulement sous Python
3.14. Reproduit en local : stable a 3.12, ~12/40 echecs a 3.14.

Course latente revelee par le fix, pas une regression de comportement.
`_handle_signal` met `_state = SOFT_STOP` synchronement mais arme l'asyncio.Event
`soft_stop_event` via `call_soon_threadsafe`, donc avec une iteration de boucle de
retard. Or `_should_stop` (le gate du scheduler entre deux tests) ne lisait QUE
l'Event. Avant le fix, `emit(TEST_END)` faisait `await run_in_threadpool` sur
chaque handler sync : un vrai point de suspension qui rendait la main a la boucle,
laquelle armait l'Event avant le prochain `_should_stop`. Handlers inline =
`await emit()` ne suspend plus jamais, on atteint le gate suivant sans yield, donc
`is_set()` encore False et le test suivant part. 3.14 change l'ordonnancement
asyncio assez pour rendre le timing perdant la plupart du temps.

Fix : `_should_stop` lit l'etat synchrone `should_stop_new_tests` (`_state !=
RUNNING`), arme des que le handler de signal tourne, independant de la boucle.
60/60 verts a 3.14 apres. C'est de toute facon le bon gate : un drapeau pose
synchroniquement ne doit pas dependre d'un call_soon_threadsafe pour etre vu.

## 2026-06-25 — bench(perf): la claim "20-30% plus vite que pytest" ne reproduit pas

Repris les benchmarks apte vs pytest pour l'article (besoin de chiffres
prouvables). Les anciennes reecritures httpx/starlette/pydantic sont perdues
(`_sandbox/dogfood` gitignore, sources supprimees, restent quelques .pyc
pre-rename `protest`). Tout reconstruit dans `benchmarks/async_concurrency/`.

Resultat principal, mesure : sur la vraie suite async httpx (`test_async_client`,
26 tests localhost) pytest est 1.20x plus RAPIDE qu'apte -n8. La claim est
inversee sur du httpx reel.

Cause, isolee sur 200 tests async sans I/O : apte fait ~8.8 ms d'overhead CPU
par test (n1), ~4 ms a n16, contre ~0.2 ms pour pytest. C'est la resolution
DI/fixtures + scopes/tasks + events + objet resultat, pas la capture (`-s` ne
change rien). La concurrence recouvre l'attente I/O d'un test mais pas cette
machinerie. Donc apte ne gagne que quand l'I/O par test depasse ~10 ms ET que
la concurrence est forte : banc Phase 1 -> 0.45x a 1ms, 1.5x a 5ms, 4.25x a
20ms (n16, 500 tests).

Pivots en cours de route : (1) approche "scenarios partages" abandonnee, le
lead voulait un port 1:1 exact de leur suite, pas ma reecriture ; (2) port async
client porte 1:1 et vert (26/26), mais le port integral des 1267 cas est
inutile, la projection (1267 x 9ms) donne ~4-5x plus lent et n'apprend rien de
plus que la loi de Phase 1.

Suite httpx COMPLETE portee 1:1 (1285 cas, 30 fichiers, 11 agents paralleles,
gaps documentes) apres le fix : 1268/1285 passent (comme le baseline), et apte
-n16 fait la suite en 1.85s vs pytest ~3.0s = 1.70x plus RAPIDE. Meme apte -n1
sequentiel est 1.4x plus rapide : la suite est majoritairement sync donc le
gain vient de l'overhead/test divise par ~20, pas de la concurrence. La claim
"20-30%" n'est pas juste rehabilitee, elle est depassee (+70%). Idem starlette
porte 1:1 (505 cas, 94% sync) : apte 1.75x plus rapide (504 passed baseline).
Deux suites reelles completes confirment.

Le banc a paye : profile cProfile -> l'overhead par test = l'event bus
(`apte/events/bus.py`) qui offload CHAQUE handler sync au threadpool via
`run_in_threadpool` (+ les meta-events HANDLER_START/END qui triplent). ~288
offloads/test, chacun un aller-retour socket + reveil kqueue. Fix teste
(handlers sync inline) : overhead 9ms -> ~0.5ms/test (x15-30), et sur la vraie
suite httpx apte passe de 1.14x plus lent a 1.11x plus RAPIDE que pytest
(483ms vs 536ms, full process). Vrai fix = inline par defaut, offload opt-in
pour les handlers bloquants ; merite son propre changement avec la suite apte.
Banc + experiment dans `benchmarks/async_concurrency/`.

## 2026-06-25 — ci: auto-publish reel (dispatch depuis release-please)

Le trigger `release: [published]` ajoute plus tot etait inoperant : release-please
cree la GitHub Release avec le GITHUB_TOKEN, et GitHub ne declenche aucun workflow
sur un evenement emis par ce token (anti-recursion). 0.3.0 et 0.3.1 ont du etre
publiees a la main.

Verifie sur les sources (changelog GitHub 2022-09-08, doc PyPI, README
release-please-action) plutot que de deviner : `workflow_dispatch` est l'EXCEPTION
a l'anti-recursion, il declenche bien un run via GITHUB_TOKEN. Et `release_created`
(singulier) est le bon output pour un composant racine.

Fix : release-please.yml fait `gh workflow run publish.yml` quand `release_created`
est vrai (+ permission `actions: write`). publish.yml reste le workflow d'entree
(claim OIDC = publish.yml, config Trusted Publisher PyPI inchangee) ; son trigger
`release:` trompeur est retire. Les prochaines releases publieront vraiment seules.

## 2026-06-25 — fix(docs): README install -> pip install apte

La section Installation du README disait encore "not yet on PyPI, install from
GitHub" alors que apte 0.3.0 est publie. Contradiction visible sur la page PyPI
(le README est la description). Bascule sur `uv add apte` / `pip install apte`.
Commit en `fix:` exprès : la description PyPI est figee a la publication, il faut
une 0.3.1 (release-please + auto-publish) pour rafraichir la page en ligne.

## 2026-06-25 — ci: run on push to main (badge CI rouge)

Badge CI rouge sur la page PyPI : pas une regression. `ci.yml` ne se declenchait
que sur `pull_request`, jamais sur push main, donc le badge fossilisait le dernier
run push (un echec de mars 2026). Ajout du trigger `push: branches: [main]` : chaque
merge relance la CI sur main et rafraichit le badge. Le code etait vert sur toutes
les PRs. (Lie : les PRs release-please n'ont aucun check car les PRs du bot
github-actions ne declenchent pas les workflows.)

## 2026-06-25 — ci(publish): apte publie sur PyPI, trigger release cable

Trusted Publisher PyPI configure (pending publisher : repo=renaudcepre/apte,
workflow=publish.yml, environment laisse sur "Any"). apte 0.3.0 publie via
workflow_dispatch manuel (build depuis main = 0.3.0), OIDC, sans token stocke.
Verifie live : pypi.org/project/apte/ 200, `pip install apte` ok, nom reserve.

publish.yml : bloc PARKED retire, trigger `release: [published]` ajoute (+ garde
workflow_dispatch). Les prochaines releases release-please publieront automatiquement.

## 2026-06-24 — fix(assets): wordmark SVG protest -> apte

Le rename texte n'avait pas touche les logos : le mot "protest" y est vectorise
en 7 paths (un par lettre, JetBrains Mono SemiBold 16px), pas en `<text>`. Donc
invisible au sed, c'est un dessin du mot.

"apte" = 4 lettres dont un "a" absent de "protest", impossible de reutiliser les
paths existants. Regenere les glyphes via fonttools + JetBrains Mono SemiBold.
Piege : verifier en comparant le premier point (moveto) est faux, l'ordre des
contours differe entre generateurs. Bon invariant = la bounding box. Calibre le
transform (scale 0.016, baseline y=38) sur le "p" du fichier, verifie les bbox
des autres lettres, puis genere "apte". Rendu controle au rasteriseur (qlmanage).

Touche `assets/logo-with-text-animate.svg` (hero README, viewBox resserree) et
`docs/assets/logo.svg` (meme artwork, non reference). uv.lock se fait re-resoudre
par chaque `uv run` sans `--no-project`, jete a chaque fois.

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
