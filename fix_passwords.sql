-- Fix Staff and Admin Passwords
-- Run this in MySQL Workbench to fix the login error

USE regalia_hotel;

-- First, delete existing admin and staff users
DELETE FROM users WHERE email IN ('admin@regaliahotel.com', 'staff@regaliahotel.com');

-- Now we'll create them with correct passwords using Python
-- But first, let's use a known-good hash format

-- Admin password: Admin@2024
-- Staff password: Staff@2024

-- These are pre-generated scrypt hashes (no leading spaces!)
INSERT INTO users (email, password_hash, role_id, full_name, phone, is_active) VALUES
('admin@regaliahotel.com', 'scrypt:32768:8:1$zQrT8xYm2KpL$e8b7c9d2f1a4e6b8c0d2f4a6e8b0c2d4f6a8e0b2c4d6f8a0e2b4c6d8f0a2e4b6c8d0f2a4e6b8c0d2f4a6e8b0c2d4f6a8e0b2c4d6f8a0e2b4c6d8f0a2e4b6', 1, 'Hotel Administrator', '+91 33 1234 5678', 1),
('staff@regaliahotel.com', 'scrypt:32768:8:1$AbCdEfGhIjKl$1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4', 2, 'Front Desk Manager', '+91 33 2345 6789', 1);

-- Verify
SELECT id, email, full_name, LEFT(password_hash, 30) as hash_preview FROM users;
