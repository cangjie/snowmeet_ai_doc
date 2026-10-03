-- 2026-10-03 上传文件迁 S3：把库里写死 mini.snowmeet.top/upload/ 的完整地址改成图片域名 img.snowmeet.top
-- 执行前提：mini 服务器 upload 目录已 sync 进 S3，且 https://img.snowmeet.top/upload/... 抽查能打开。
-- mini_upload.file_path_name / thumb 及 school_*、ski_pass.card_image_url 存的是相对路径 /upload/...，不用改。
-- 指向已注销 snowmeet.wanlonghuaxue.com 的 3 行（mini_upload 88999/89023 的 thumb、rent_product_image 306）文件已不存在，不动。
-- 2026-10-03 只读统计：care.images 7779 行、product_image.image_url 3、rent_list.guarantee_credit_photos 5、
-- rent_list_detail.images 15、rent_product_image.image_url 1。
-- ✅ 2026-10-03 已在生产执行（用户确认）：备份 5 张 bak_20261003_* 表后改写 7803 行，剩余 0、与备份逐行比对一致，已 COMMIT。

SET XACT_ABORT ON;

-- 1. 预览：各列待改行数
SELECT 'care.images' col, COUNT(*) n FROM care WHERE images LIKE '%://mini.snowmeet.top/upload/%'
UNION ALL SELECT 'product_image.image_url', COUNT(*) FROM product_image WHERE image_url LIKE '%://mini.snowmeet.top/upload/%'
UNION ALL SELECT 'rent_list.guarantee_credit_photos', COUNT(*) FROM rent_list WHERE guarantee_credit_photos LIKE '%://mini.snowmeet.top/upload/%'
UNION ALL SELECT 'rent_list_detail.images', COUNT(*) FROM rent_list_detail WHERE images LIKE '%://mini.snowmeet.top/upload/%'
UNION ALL SELECT 'rent_product_image.image_url', COUNT(*) FROM rent_product_image WHERE image_url LIKE '%://mini.snowmeet.top/upload/%';

-- 2. 备份原值（只备份要改的行；回滚见文末）
SELECT id, images INTO bak_20261003_care_images FROM care WHERE images LIKE '%://mini.snowmeet.top/upload/%';
SELECT id, image_url INTO bak_20261003_product_image FROM product_image WHERE image_url LIKE '%://mini.snowmeet.top/upload/%';
SELECT id, guarantee_credit_photos INTO bak_20261003_rent_list FROM rent_list WHERE guarantee_credit_photos LIKE '%://mini.snowmeet.top/upload/%';
SELECT id, images INTO bak_20261003_rent_list_detail FROM rent_list_detail WHERE images LIKE '%://mini.snowmeet.top/upload/%';
SELECT id, image_url INTO bak_20261003_rent_product_image FROM rent_product_image WHERE image_url LIKE '%://mini.snowmeet.top/upload/%';

-- 3. 改写（http 与 https 都统一成 https://img.snowmeet.top/upload/）
BEGIN TRAN;
UPDATE care SET images = REPLACE(REPLACE(images, 'https://mini.snowmeet.top/upload/', 'https://img.snowmeet.top/upload/'), 'http://mini.snowmeet.top/upload/', 'https://img.snowmeet.top/upload/')
  WHERE images LIKE '%://mini.snowmeet.top/upload/%';
UPDATE product_image SET image_url = REPLACE(REPLACE(image_url, 'https://mini.snowmeet.top/upload/', 'https://img.snowmeet.top/upload/'), 'http://mini.snowmeet.top/upload/', 'https://img.snowmeet.top/upload/')
  WHERE image_url LIKE '%://mini.snowmeet.top/upload/%';
UPDATE rent_list SET guarantee_credit_photos = REPLACE(REPLACE(guarantee_credit_photos, 'https://mini.snowmeet.top/upload/', 'https://img.snowmeet.top/upload/'), 'http://mini.snowmeet.top/upload/', 'https://img.snowmeet.top/upload/')
  WHERE guarantee_credit_photos LIKE '%://mini.snowmeet.top/upload/%';
UPDATE rent_list_detail SET images = REPLACE(REPLACE(images, 'https://mini.snowmeet.top/upload/', 'https://img.snowmeet.top/upload/'), 'http://mini.snowmeet.top/upload/', 'https://img.snowmeet.top/upload/')
  WHERE images LIKE '%://mini.snowmeet.top/upload/%';
UPDATE rent_product_image SET image_url = REPLACE(REPLACE(image_url, 'https://mini.snowmeet.top/upload/', 'https://img.snowmeet.top/upload/'), 'http://mini.snowmeet.top/upload/', 'https://img.snowmeet.top/upload/')
  WHERE image_url LIKE '%://mini.snowmeet.top/upload/%';
-- 4. 核对：以下应全部为 0，再 COMMIT；不对就 ROLLBACK
SELECT
  (SELECT COUNT(*) FROM care WHERE images LIKE '%://mini.snowmeet.top/upload/%')
+ (SELECT COUNT(*) FROM product_image WHERE image_url LIKE '%://mini.snowmeet.top/upload/%')
+ (SELECT COUNT(*) FROM rent_list WHERE guarantee_credit_photos LIKE '%://mini.snowmeet.top/upload/%')
+ (SELECT COUNT(*) FROM rent_list_detail WHERE images LIKE '%://mini.snowmeet.top/upload/%')
+ (SELECT COUNT(*) FROM rent_product_image WHERE image_url LIKE '%://mini.snowmeet.top/upload/%') AS remaining;
-- COMMIT;  -- 核对无误后手动执行
-- ROLLBACK;

-- 回滚（COMMIT 之后才需要）：
-- UPDATE c SET c.images = b.images FROM care c JOIN bak_20261003_care_images b ON b.id = c.id;
-- UPDATE p SET p.image_url = b.image_url FROM product_image p JOIN bak_20261003_product_image b ON b.id = p.id;
-- UPDATE r SET r.guarantee_credit_photos = b.guarantee_credit_photos FROM rent_list r JOIN bak_20261003_rent_list b ON b.id = r.id;
-- UPDATE d SET d.images = b.images FROM rent_list_detail d JOIN bak_20261003_rent_list_detail b ON b.id = d.id;
-- UPDATE p SET p.image_url = b.image_url FROM rent_product_image p JOIN bak_20261003_rent_product_image b ON b.id = p.id;
