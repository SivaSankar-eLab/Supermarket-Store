-- Enable pg_trgm for fuzzy product search (runs once at DB init)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
