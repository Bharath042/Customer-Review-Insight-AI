CREATE DATABASE IF NOT EXISTS customer_review_db;

-- Drop user if exists to ensure a clean slate, especially if password was mismatched
DROP USER IF EXISTS 'customer_review'@'%';

-- Create user with caching_sha2_password authentication which is default for MySQL 8+
-- REPLACE 'admin@123' with the actual un-encoded password from your .env
-- Docker Compose will pass the DECODED password to the container via MYSQL_PASSWORD
-- The app will connect using the ENCODED password, but the DB expects the actual password
CREATE USER 'customer_review'@'%' IDENTIFIED WITH caching_sha2_password BY 'admin@123';

-- Grant all privileges to the user on the specific database
GRANT ALL PRIVILEGES ON customer_review_db.* TO 'customer_review'@'%';

FLUSH PRIVILEGES;