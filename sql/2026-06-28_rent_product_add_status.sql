IF COL_LENGTH('rent_product', 'status') IS NULL
BEGIN
    ALTER TABLE rent_product ADD status NVARCHAR(20) NULL;
END
GO
