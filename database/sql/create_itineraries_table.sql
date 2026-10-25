CREATE SCHEMA IF NOT EXISTS optimapper;

CREATE TABLE IF NOT EXISTS optimapper.itineraries (
    uuid UUID PRIMARY KEY,
    city TEXT NOT NULL,
    country TEXT,
    number_of_days INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    itinerary JSONB NOT NULL
);

-- Safe to run on an existing installation; old itineraries remain readable.
ALTER TABLE optimapper.itineraries
    ADD COLUMN IF NOT EXISTS number_of_days INTEGER;
