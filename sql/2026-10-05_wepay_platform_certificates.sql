-- Platform certificate serials and complete PEMs are stored together as a JSON array.
-- Apply before deploying the API model. NULL preserves legacy cert/disk lookup.
SET XACT_ABORT ON;
BEGIN TRANSACTION;
IF COL_LENGTH('dbo.wepay_key', 'platform_certificates') IS NULL
    ALTER TABLE dbo.wepay_key ADD platform_certificates nvarchar(max) NULL;
COMMIT TRANSACTION;

-- Format: [{"serial_no":"<platform serial>","certificate":"<full PEM>"}, ...]
-- This is distinct from key_serial/private_key (merchant request signing).
-- Retain overlapping valid certificates until WeChat no longer uses the old serial.
-- Populate with a parameterized UPDATE; never put private keys in this file.
