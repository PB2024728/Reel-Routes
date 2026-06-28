"""Shared Pydantic models — the contract between backend and frontend."""
from typing import Optional
from pydantic import BaseModel


class GeoSuggestion(BaseModel):
    label: str          # "Alpharetta, GA 30009"
    secondary: str      # full display string
    lat: float
    lng: float
    kind: str           # "city" | "zip" | "address"


class Deadline(BaseModel):
    label: str          # "Early", "Regular", "Late"
    date: str           # ISO yyyy-mm-dd


class Festival(BaseModel):
    id: int
    name: str
    city: str
    lat: float
    lng: float
    tier: int
    genres: list[str]
    max_runtime: int
    accept_rate: float
    base_fee: int
    deadlines: list[Deadline]
    oscar_qual: bool
    attendees: int
    filmfreeway_url: str
    airport: str
    # computed per-request
    dist_mi: Optional[float] = None
    fit: Optional[int] = None


class FlightOffer(BaseModel):
    carrier: str
    price: float
    stops: int
    depart: str
    duration: str
    booking_url: str
    live: bool


class HotelOffer(BaseModel):
    name: str
    nightly: float
    dist_mi: float
    rating: Optional[float] = None
    booking_url: str
    live: bool


class CarRental(BaseModel):
    vendor: str
    car_class: str
    daily: float
    booking_url: str
    live: bool


class RideshareEstimate(BaseModel):
    service: str        # "Uber" | "Lyft"
    est_low: float
    est_high: float
    distance_mi: float
    deeplink: str       # opens the app pre-filled
    note: str
