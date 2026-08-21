from app.discovery.classify import classify_crypt14, is_trashed
from app.models import Crypt14Kind


def test_is_trashed():
    assert is_trashed(".trashed-IMG_0001.jpg")
    assert is_trashed(".TRASHED-foo.png")  # case-insensitive
    assert not is_trashed("IMG_0001.jpg")


def test_classify_crypt14_current_vs_historical():
    assert classify_crypt14("msgstore.db.crypt14") == Crypt14Kind.CURRENT
    assert classify_crypt14("msgstore-increment-1.db.crypt14") == Crypt14Kind.CURRENT
    assert classify_crypt14("msgstore-2026-08-14.1.db.crypt14") == Crypt14Kind.HISTORICAL
    assert classify_crypt14("msgstore-increment-1-2026-08-20.1.db.crypt14") == Crypt14Kind.HISTORICAL
    assert classify_crypt14("regular_photo.jpg") is None
