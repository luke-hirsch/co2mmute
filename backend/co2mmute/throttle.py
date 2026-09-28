"""Rate limiting for the three doors that can be guessed at.

There was none anywhere before S9: `/accounts/login/` took unlimited password
guesses, `/accounts/signup/` unlimited accounts, and `api/game/seat/<code>/`
unlimited tries at a six-character code. `ChatConsumer` was the only
rate-limited thing in the backend, and it limits its own traffic rather than an
attacker's.

**A fixed window in the cache, not a dependency.** django-axes would bring a
model, a migration, an admin and a lock-out UI for a project whose entire
attack surface is three endpoints and whose research group inherits every
package in `requirements.txt`. Redis is already the cache, and a window counter
is `incr` plus an expiry.

**What gets counted is the whole design.** A classroom sits behind one school
NAT: every phone in the room is one address, so counting *attempts* would
throttle a class for playing the game.

- the seat code and the login count **failures**. A class redeeming real codes
  is never counted at all, and a guesser produces nothing but misses.
- the sign-up counts **successes**, because a failed sign-up has guessed at
  nothing and the only abuse worth stopping is mass account creation. Locking
  somebody out of their own sign-up for mistyping a password twice is the one
  thing this must not do.

**No address is stored.** `client_key` hashes it with a `SECRET_KEY` salt, so
what sits in Redis for the window is a digest nobody can read back — the same
data minimisation the rest of the project is built on, and what lets
`legal/dsgvo.html` describe it in a sentence. Rotating `SECRET_KEY` empties
every counter, which is harmless: they are all minutes long.
"""

from django.core.cache import cache
from django.utils.crypto import salted_hmac

# ── the dials ────────────────────────────────────────────────────────────────
# Generous on purpose. These stop a script, not a person: a human at a keyboard
# cannot reach any of them, and the numbers below leave 887 million codes and a
# password space untouched by anything under a distributed attack.

#: Wrong passwords from one address before it is shut out, and for how long.
LOGIN_LIMIT = 10
LOGIN_WINDOW = 15 * 60

#: Accounts one address may create per hour.
SIGNUP_LIMIT = 10
SIGNUP_WINDOW = 60 * 60

#: Misses on `seat/<code>/` per address. The window is the code's own lifetime
#: (`game.seats.CODE_TTL`), so a guesser never gets two windows at one code.
SEAT_CODE_LIMIT = 20
SEAT_CODE_WINDOW = 5 * 60


def client_key(request) -> str:
    """A stable, unreadable handle for the address a request came from.

    `X-Real-IP` and not `X-Forwarded-For`: nginx sets the first from
    `$remote_addr`, overwriting whatever the client sent, while the second is
    `$proxy_add_x_forwarded_for` — it *appends* to the client's own header, so
    its leftmost entry is attacker-controlled and trusting it would hand every
    request a fresh quota. `REMOTE_ADDR` is the fallback for the dev stack,
    where Vite proxies without setting either.
    """
    address = request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR", "")
    return salted_hmac("co2mmute.throttle", address.strip()).hexdigest()[:32]


def _key(scope: str, key: str) -> str:
    return f"throttle:{scope}:{key}"


def record(scope: str, key: str, window: int) -> int:
    """Count one event. Returns the count inside the current window.

    `add` then `incr`, because Django's cache has no "increment or create":
    `add` writes only a missing key, so the expiry is set exactly once and the
    window really is fixed rather than sliding forward on every hit — which
    would let a steady trickle keep somebody shut out for ever.
    """
    stamp = _key(scope, key)
    if cache.add(stamp, 1, window):
        return 1
    try:
        return cache.incr(stamp)
    except ValueError:
        # It expired between the add and the incr. Start the window again.
        cache.add(stamp, 1, window)
        return 1


def over_limit(scope: str, key: str, limit: int) -> bool:
    """Has this key used the window up? Counts nothing itself.

    `>=`, so `LOGIN_LIMIT = 10` means ten wrong passwords and then the door
    shuts — not eleven.
    """
    return (cache.get(_key(scope, key)) or 0) >= limit


def clear(scope: str, key: str) -> None:
    """Forget the count. A right password drops the wrong ones before it, so a
    host who fumbles four times and then gets in is not locked out afterwards."""
    cache.delete(_key(scope, key))
