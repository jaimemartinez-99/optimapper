CREATE SCHEMA IF NOT EXISTS optimapper;

CREATE TABLE optimapper.itineraries (
    uuid UUID PRIMARY KEY,
    city TEXT NOT NULL,
    country TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    itinerary JSONB NOT NULL
);
