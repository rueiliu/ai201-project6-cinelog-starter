"""
tests/test_watchlist.py — CineLog

Tests for the watchlist service. These mirror the structure of
tests/test_collection.py (same fixtures, same assertion style).
"""

import pytest
from app import create_app, db
from models import User, Film, WatchlistEntry
from services.watchlist_service import (
    add_to_watchlist,
    remove_from_watchlist,
    get_watchlist,
    AlreadyInWatchlistError,
    NotInWatchlistError,
)
from services.collection_service import FilmNotFoundError


@pytest.fixture
def app():
    """Create an isolated test app with an in-memory database."""
    app = create_app(config={
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def sample_user(app):
    """A user to use in tests."""
    with app.app_context():
        user = User(username="testuser", email="test@example.com")
        db.session.add(user)
        db.session.commit()
        return user.id


@pytest.fixture
def sample_film(app):
    """A film to use in tests."""
    with app.app_context():
        film = Film(title="Paddington 2", year=2017, genre="Comedy")
        db.session.add(film)
        db.session.commit()
        return film.id


# ── Nonexistent film ─────────────────────────────────────────────────────────

def test_add_to_watchlist_nonexistent_film_raises(app, sample_user):
    """
    Adding a film_id that doesn't exist in the database should raise
    FilmNotFoundError, not a database integrity error.

    Equivalent of test_add_to_collection_nonexistent_film_raises.
    """
    with app.app_context():
        fake_film_id = "00000000-0000-0000-0000-000000000000"

        with pytest.raises(FilmNotFoundError):
            add_to_watchlist(user_id=sample_user, film_id=fake_film_id)


# ── Visibility toggle ────────────────────────────────────────────────────────

def test_add_to_watchlist_defaults_to_public(app, sample_user, sample_film):
    """
    With no public argument, an entry should default to public=True
    (the documented visibility default — see Comment 4).
    """
    with app.app_context():
        entry = add_to_watchlist(user_id=sample_user, film_id=sample_film)
        assert entry.public is True


def test_add_to_watchlist_respects_public_false(app, sample_user, sample_film):
    """
    Passing public=False should create a private watchlist entry, letting
    callers set visibility explicitly instead of relying on the default.
    """
    with app.app_context():
        entry = add_to_watchlist(
            user_id=sample_user, film_id=sample_film, public=False
        )
        assert entry.public is False


# ── Remove ───────────────────────────────────────────────────────────────────

def test_remove_from_watchlist_deletes_entry(app, sample_user, sample_film):
    """
    Removing a film that is on the watchlist should delete the entry and
    return True. Mirrors remove_from_collection.
    """
    with app.app_context():
        add_to_watchlist(user_id=sample_user, film_id=sample_film)

        result = remove_from_watchlist(user_id=sample_user, film_id=sample_film)

        assert result is True
        remaining = WatchlistEntry.query.filter_by(
            user_id=sample_user, film_id=sample_film
        ).count()
        assert remaining == 0


def test_remove_from_watchlist_not_present_raises(app, sample_user, sample_film):
    """
    Removing a film that is not on the watchlist should raise
    NotInWatchlistError, not silently succeed.
    """
    with app.app_context():
        with pytest.raises(NotInWatchlistError):
            remove_from_watchlist(user_id=sample_user, film_id=sample_film)
