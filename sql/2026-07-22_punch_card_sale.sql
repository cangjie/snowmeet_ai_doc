-- 租赁次卡销售功能：新增字段 DDL
-- 对应 SnowmeetApi 改动：Models/Product.cs (punch_total) / Models/Order/Retail.cs (product_id, punch_card_id) / Models/Rent/PunchCard.cs (source_retail_id)
-- 部署顺序：先在生产库执行本脚本，再部署新版 SnowmeetApi（EF 加字段后所有相关查询默认 SELECT 该列，不先加列会让查询全挂）

ALTER TABLE dbo.product ADD punch_total INT NULL;

ALTER TABLE dbo.retail ADD product_id INT NULL;
ALTER TABLE dbo.retail ADD punch_card_id INT NULL;
ALTER TABLE dbo.retail ADD CONSTRAINT FK_retail_product
    FOREIGN KEY (product_id) REFERENCES dbo.product(id);
ALTER TABLE dbo.retail ADD CONSTRAINT FK_retail_punch_card
    FOREIGN KEY (punch_card_id) REFERENCES dbo.punch_card(id);

ALTER TABLE dbo.punch_card ADD source_retail_id INT NULL;
ALTER TABLE dbo.punch_card ADD CONSTRAINT FK_punch_card_source_retail
    FOREIGN KEY (source_retail_id) REFERENCES dbo.retail(id);
