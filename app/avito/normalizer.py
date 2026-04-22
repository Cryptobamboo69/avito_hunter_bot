from __future__ import annotations

from app.models import Listing
from app.utils.text import normalize_text


def normalize_listing(listing: Listing) -> Listing:
    listing.title = normalize_text(listing.title)
    if listing.description:
        listing.description = normalize_text(listing.description)
    if listing.location:
        listing.location = normalize_text(listing.location)
    if listing.seller_name:
        listing.seller_name = normalize_text(listing.seller_name)
    return listing
