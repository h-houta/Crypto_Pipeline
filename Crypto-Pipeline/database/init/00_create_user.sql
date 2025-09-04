-- Create crypto_user if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'crypto_user') THEN
        CREATE USER crypto_user WITH PASSWORD 'cryptopass123';
    END IF;
END
$$;

-- Grant necessary permissions to crypto_user
GRANT CONNECT ON DATABASE crypto_db TO crypto_user;
GRANT USAGE ON SCHEMA public TO crypto_user;
GRANT CREATE ON SCHEMA public TO crypto_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO crypto_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO crypto_user;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO crypto_user;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO crypto_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO crypto_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO crypto_user;

-- Grant TimescaleDB specific permissions
GRANT USAGE ON SCHEMA timescaledb_information TO crypto_user;
GRANT SELECT ON ALL TABLES IN SCHEMA timescaledb_information TO crypto_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA timescaledb_information TO crypto_user;
