"""Finding out that a newer release exists, and (phase 2) installing it.

Split deliberately from everything else: this is the only part of the app
that talks to a server, and the only part that would ever run a downloaded
executable. Keeping it in one package makes those two facts auditable.
"""
