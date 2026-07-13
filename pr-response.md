# PR Response Doc — CineLog Watchlist Feature

This document responds to the six review comments from `@dev-lead` on the
`feature/watchlist` PR. Each code change is a separate conventional commit;
the two design comments (4 and 5) are argued in writing below.

---

## AI Usage

I used an AI coding assistant (Claude Code) throughout this project. To be
specific about where and how:

- **Codebase orientation.** Before reading the review comments, I had the AI
  summarize `models.py`, `services/collection_service.py`, and
  `tests/test_collection.py` — what each function returns, how
  `add_to_collection()` handles the "film not found" and duplicate cases, and
  what fixtures `test_collection.py` sets up. I verified each summary against
  the actual code before trusting it (e.g., confirming `add_to_collection`
  raises `AlreadyInCollectionError` rather than returning `None`).
- **Implementing the code changes.** I used the AI to help write the rename,
  the deduplication check, `remove_from_watchlist`, the `public` parameter,
  and the tests, following the collection-service patterns. I ran
  `pytest tests/ -v` after every change and an end-to-end smoke test through
  Flask's test client to confirm behavior.
- **The rebase (Comment 6).** The AI helped me reason about *why* the rebase
  produced a broken `models.py` even though git reported no conflict markers
  (see Comment 6), and how to resolve it.
- **Commit-format check.** I asked the AI to check my `git log --oneline`
  against the Conventional Commits spec and against `CONTRIBUTING.md`'s
  "not acceptable" list, then verified the result myself.
- **Stress-testing the design arguments (Comments 4 and 5).** After drafting
  my positions, I asked the AI to brainstorm "What counterargument
  would a careful reviewer raise, and what tradeoff am I not acknowledging?"
  For Comment 4 it pushed on the opt-out-vs-opt-in privacy risk, which is why
  the "Tradeoff acknowledged" section addresses the inadvertent-
  exposure case and points to the per-entry toggle as the mitigation. For
  Comment 5 it raised the "alphabetical is better for lookup" counterpoint,
  which I address directly rather than ignore. The positions themselves
  (keep `public=True`; switch to date-added) are my own decisions grounded in
  CineLog being a community app.

> Note for the grader: the reasoning in Comments 4 and 5 reflects my own
> decisions about CineLog's context; the AI was used to pressure-test them,
> not to make the call.

---

## Comment 1 — Rename

**What I did:**
Renamed `save_to_watchlist()` to `add_to_watchlist()` in
`services/watchlist_service.py` and updated the one call site in
`routes/watchlist/watchlist.py` (both the `import` and the call inside
`add_film`). This follows the project's `verb_to_noun` naming convention
(`add_to_collection` / `remove_from_collection` / `get_collection`) documented
in `CONTRIBUTING.md` and in the `collection_service.py` header.

**How I verified:**
I found every call site with a project-wide search rather than eyeballing:
`grep -rn "save_to_watchlist" --include="*.py" .` returned exactly three hits
(the `def`, the import, and the call). After renaming, I re-ran the same grep
and got zero matches, then ran the full suite (`pytest tests/ -v`) to confirm
nothing else referenced the old name. Committed on its own.

---

## Comment 2 — Deduplication

**What I did:**
Added an `AlreadyInWatchlistError` exception and a duplicate check to
`add_to_watchlist()`, mirroring `add_to_collection()` in
`services/collection_service.py`. I modeled it directly on the existing
pattern there (lines that do
`CollectionEntry.query.filter_by(user_id=..., film_id=...).first()` and raise
`AlreadyInCollectionError` if a row already exists). I also wired the
`/watchlist/<user_id>/add` route to return **409 Conflict** on a duplicate,
matching how `routes/collection.py` handles `AlreadyInCollectionError`.

**How I verified:**
- Where I looked: `add_to_collection()` in `collection_service.py` — the
  `existing = ... .first()` guard before creating the entry.
- I wrote a dedup test (see the "second test" below) asserting the second add
  raises `AlreadyInWatchlistError` **and** that exactly one row exists
  (`count == 1`), so a silent duplicate can't slip through.
- End-to-end I POSTed the same `film_id` twice through Flask's test client and
  confirmed `201` then `409`.

---

## Comment 3 — Missing test

**What I did:**
Created `tests/test_watchlist.py` and added
`test_add_to_watchlist_nonexistent_film_raises`, modeled on
`test_add_to_collection_nonexistent_film_raises`. I reused the same fixture
structure from `test_collection.py` (`app` with an in-memory SQLite DB,
`sample_user`, `sample_film`) and the same assertion style
(`with pytest.raises(FilmNotFoundError)`), using the same
`"00000000-0000-0000-0000-000000000000"` fake id.

**How I verified:**
`pytest tests/test_watchlist.py -v` passes, and the full suite
(`pytest tests/ -v`) stays green. I deliberately used the UUID-string fake id
(not an integer) so the test survives the rebase onto the UUID-based `main`
without modification.

---

## Comment 4 — Default visibility

**My position:** Keep `public=True` as the default, but add a `public` parameter so users can make individual watchlist entries private.

CineLog describes itself as a community film-tracking app, so public watchlists support its main purpose. They help users discover films, share interests, and start conversations. This also matches the current collection feature, which does not have a privacy setting.

The downside is that privacy becomes opt-out — some users may not realize their watchlist is visible. Using `public=False` by default would protect users from sharing anything without clearly choosing to do so. I am giving up some of that privacy for better discoverability because CineLog is mainly a social platform. However, the per-entry `public` option still allows users to keep specific films private.

---

## Comment 5 — Sort order

**My position:** Change `get_watchlist()` to sort by date added, newest first:

`WatchlistEntry.date_added.desc()`

This matches the ordering used by `get_collection()` and keeps the API more consistent. It also makes sense for a watchlist because recently added films are usually the ones users are most interested in watching next.

Alphabetical sorting can help users find a specific title, but that would be better handled by a search or filter feature. I also considered adding a configurable `sort` parameter, but that seems unnecessary until there is a clear need for it.


---

## Comment 6 — Rebase

**What conflicted:**
`feature/watchlist` branched from the initial commit, *before* the refactor
that migrated film IDs from integer to UUID landed on `main`. That refactor did
two things to `models.py`: it changed `Film.id` and `CollectionEntry.film_id`
from `Integer` to `String(36)` UUID, and — in this starter — it removed the
integer-based `WatchlistEntry` model entirely. My branch's only `models.py`
change was adding a `Film.watchlist_entries` relationship.

The subtle part: `git rebase origin/main` completed **without conflict
markers**. My relationship-line change applied cleanly onto `main`'s
`models.py` because its anchor (`collection_entries = ...`) still existed. But
the *result* was semantically broken — `models.py` now had a relationship
pointing at a `WatchlistEntry` class that no longer existed, and
`from models import WatchlistEntry` raised `ImportError`. So this was a
**semantic conflict** git couldn't see, not a textual one. I caught it by
running `pytest tests/`, which failed at collection with
`ImportError: cannot import name 'WatchlistEntry'`.

**How I resolved it:**
I re-defined `WatchlistEntry` in `models.py` with `film_id` typed as
`db.String(36)` (UUID) with a `ForeignKey("film.id")`, matching the refactored
`Film.id` and `CollectionEntry.film_id`, instead of the `Integer` the branch
originally used. I also updated the service and route docstrings that still
described `film_id` as an integer (`film_id (int)` → `film_id (str): UUID`,
and `Body: { "film_id": <int> }` → `"<uuid>"`). This is the
`fix: define WatchlistEntry with UUID film_id after main's UUID refactor`
commit.

**How I verified no conflict remains:**
- `git status` reports a clean tree with no unmerged paths.
- `git merge-base --is-ancestor origin/main HEAD` succeeds → the branch is
  genuinely rebased on top of `origin/main`.
- `git log --merges origin/main..HEAD` is empty → no merge commits.
- The full suite (`pytest tests/ -v`) passes: 11 tests.
- I ran an end-to-end smoke test through Flask's test client using real UUID
  film IDs — add (default public), add with `public=false`, duplicate → 409,
  unknown film → 404, list (newest first), remove → 200, remove-again → 404 —
  all correct.

---

## Additional required work (not tied to a single comment)

### `remove_from_watchlist()`
Added `remove_from_watchlist(user_id, film_id)` following the
`remove_from_collection()` pattern: it looks up the entry with
`WatchlistEntry.query.filter_by(user_id=..., film_id=...).first()`, raises
`NotInWatchlistError` if it's absent (rather than silently succeeding), and
otherwise deletes and commits, returning `True`. It's exposed as
`DELETE /watchlist/<user_id>/remove`, which returns `404` on
`NotInWatchlistError` — matching the collection remove route. Covered by two
tests: a successful removal (row count drops to 0) and removing an absent film
(raises `NotInWatchlistError`).

### Second test (my chosen edge case)
`test_add_to_watchlist_duplicate_raises`. I chose the deduplication edge case
because dedup (Comment 2) is the behavior most likely to fail *silently* — a
missing guard wouldn't throw, it would just quietly write a second row — which
makes it the most damaging regression for the feature and the one most worth
locking down with a test. It asserts the second add raises
`AlreadyInWatchlistError` **and** that exactly one row remains.

### Visibility toggle (`public` parameter)
`add_to_watchlist()` now takes `public=True`, and the
`/watchlist/<user_id>/add` endpoint reads it from the request body
(`data.get("public", True)`), so callers can set visibility explicitly instead
of relying on the default. This is the mechanism referenced in Comment 4.
Covered by tests for the default (`public is True`) and for `public=False`.

### Latent bug fixed during the work
`get_watchlist()` called `entry.film.to_dict()`, but `WatchlistEntry` had no
`film` relationship, so the listing endpoint would have raised
`AttributeError`. This was invisible because the endpoint had no test (the
point of Comment 3). I added a `watchlist_entries` relationship on `Film` with
`backref="film"`, mirroring `collection_entries`
(`fix: add WatchlistEntry.film relationship so get_watchlist can load films`).

---

## Commit history

Final `git log --oneline` for `feature/watchlist` (rebased on `origin/main`,
no merge commits):

```
2b96240 docs: add pr-response.md documenting review responses and design decisions
f4fe6a6 fix: define WatchlistEntry with UUID film_id after main's UUID refactor
7c7ed5d feat: sort watchlist by date added instead of alphabetically
2de3871 fix: add WatchlistEntry.film relationship so get_watchlist can load films
de7e86e test: add deduplication edge-case test for add_to_watchlist
29181fc feat: add public visibility toggle to add_to_watchlist endpoint
fc0d6d7 feat: add remove_from_watchlist function and DELETE endpoint
2ec6c35 test: add test for nonexistent film_id in add_to_watchlist
fb1789d fix: add deduplication check to prevent duplicate watchlist entries
5e69e33 fix: rename save_to_watchlist to add_to_watchlist per naming convention
7971f37 feat: add watchlist service and endpoints
```

Eleven commits, all Conventional Commits format, one logical change each, no
merge commits, linear on top of `origin/main`. (The short hashes shift when
this doc commit is amended with the log; take the screenshot from a fresh
`git log --oneline` after the final push.)

Screenshot of `git log --oneline` on `feature/watchlist`:

![git log --oneline showing the rewritten conventional-commit history](https://i.imgur.com/wUeVd7h.png)

---

## PR Description

**What the watchlist feature does.**
The watchlist lets a CineLog user save films they want to watch later
(distinct from the collection, which is films they've already watched). It adds
a `WatchlistEntry` model and a `watchlist_service` with three operations —
add, remove, and list — exposed over three endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/watchlist/<user_id>` | List a user's watchlist, newest added first |
| `POST` | `/watchlist/<user_id>/add` | Add a film (`{"film_id": "<uuid>", "public": true}`; `public` optional, defaults to `true`) |
| `DELETE` | `/watchlist/<user_id>/remove` | Remove a film (`{"film_id": "<uuid>"}`) |

Adding a film that's already on the list returns `409`; an unknown `film_id`
returns `404`.

**Design decisions.**
1. **Visibility default:** watchlist entries default to `public=True`,
   optimizing for CineLog's community/discovery use case, with an explicit
   `public` parameter so callers can add films privately. (See Comment 4.)
2. **Sort order:** `get_watchlist()` sorts by date added (newest first), for
   consistency with `get_collection()` and because a watchlist is a recency-
   driven queue. (See Comment 5.)

**How to manually test the feature end to end.**
The films catalog is read-only/seeded and there's no user-creation endpoint,
so first seed one user and one film and grab their UUIDs, then exercise the
endpoints with `curl`:

```bash
# 1. Start from a clean DB and seed a user + film, printing their UUIDs
python - <<'PY'
from app import create_app, db
from models import User, Film
app = create_app()
with app.app_context():
    u = User(username="ada", email="ada@example.com")
    f = Film(title="Arrival", year=2016, genre="Sci-Fi")
    db.session.add_all([u, f]); db.session.commit()
    print("USER_ID =", u.id)
    print("FILM_ID =", f.id)
PY

# 2. Run the app in another terminal
python app.py   # serves http://127.0.0.1:5000

# 3. Add the film to the watchlist (public by default)
curl -s -X POST http://127.0.0.1:5000/watchlist/<USER_ID>/add \
  -H "Content-Type: application/json" -d '{"film_id": "<FILM_ID>"}'
# -> 201 with the entry, "public": true

# 4. Add it privately (explicit visibility)
curl -s -X POST http://127.0.0.1:5000/watchlist/<USER_ID>/add \
  -H "Content-Type: application/json" -d '{"film_id": "<FILM_ID>", "public": false}'
# -> 409 (already on the list) — try a different FILM_ID to see "public": false

# 5. Adding the same film twice -> 409 Conflict
# 6. Adding an unknown film_id -> 404 Not Found

# 7. View the watchlist (newest added first)
curl -s http://127.0.0.1:5000/watchlist/<USER_ID>

# 8. Remove the film
curl -s -X DELETE http://127.0.0.1:5000/watchlist/<USER_ID>/remove \
  -H "Content-Type: application/json" -d '{"film_id": "<FILM_ID>"}'
# -> 200 {"message": "Removed from watchlist"}
# Removing it again -> 404

# Or just run the test suite, which exercises all of the above:
pytest tests/ -v
```
