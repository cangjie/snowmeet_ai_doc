-- 次卡使用记录回补：punch_card_used INSERT + punch_card.punches 重算
-- 自动回补 = 会员恰好 1 张租赁卡 & settled=1，每条 rental 一行
-- 幂等：INSERT 用 NOT EXISTS 守卫；punches 用 SUM 重算
BEGIN TRAN;

INSERT INTO punch_card_used (card_id, order_id, biz_type, biz_id, payment_id, punch_count, valid, create_date)
SELECT 12, 45585, N'租赁', 3080, NULL, 2, 1, GETDATE()
WHERE NOT EXISTS (SELECT 1 FROM punch_card_used WHERE biz_type=N'租赁' AND biz_id=3080 AND valid=1);
INSERT INTO punch_card_used (card_id, order_id, biz_type, biz_id, payment_id, punch_count, valid, create_date)
SELECT 12, 45585, N'租赁', 3081, NULL, 2, 1, GETDATE()
WHERE NOT EXISTS (SELECT 1 FROM punch_card_used WHERE biz_type=N'租赁' AND biz_id=3081 AND valid=1);
INSERT INTO punch_card_used (card_id, order_id, biz_type, biz_id, payment_id, punch_count, valid, create_date)
SELECT 14, 62586, N'租赁', 17561, NULL, 1, 1, GETDATE()
WHERE NOT EXISTS (SELECT 1 FROM punch_card_used WHERE biz_type=N'租赁' AND biz_id=17561 AND valid=1);
INSERT INTO punch_card_used (card_id, order_id, biz_type, biz_id, payment_id, punch_count, valid, create_date)
SELECT 14, 62586, N'租赁', 17562, NULL, 1, 1, GETDATE()
WHERE NOT EXISTS (SELECT 1 FROM punch_card_used WHERE biz_type=N'租赁' AND biz_id=17562 AND valid=1);
INSERT INTO punch_card_used (card_id, order_id, biz_type, biz_id, payment_id, punch_count, valid, create_date)
SELECT 15, 62589, N'租赁', 17573, NULL, 1, 1, GETDATE()
WHERE NOT EXISTS (SELECT 1 FROM punch_card_used WHERE biz_type=N'租赁' AND biz_id=17573 AND valid=1);
INSERT INTO punch_card_used (card_id, order_id, biz_type, biz_id, payment_id, punch_count, valid, create_date)
SELECT 15, 62589, N'租赁', 17574, NULL, 1, 1, GETDATE()
WHERE NOT EXISTS (SELECT 1 FROM punch_card_used WHERE biz_type=N'租赁' AND biz_id=17574 AND valid=1);
INSERT INTO punch_card_used (card_id, order_id, biz_type, biz_id, payment_id, punch_count, valid, create_date)
SELECT 15, 62809, N'租赁', 18307, NULL, 1, 1, GETDATE()
WHERE NOT EXISTS (SELECT 1 FROM punch_card_used WHERE biz_type=N'租赁' AND biz_id=18307 AND valid=1);
INSERT INTO punch_card_used (card_id, order_id, biz_type, biz_id, payment_id, punch_count, valid, create_date)
SELECT 15, 62939, N'租赁', 18446, NULL, 1, 1, GETDATE()
WHERE NOT EXISTS (SELECT 1 FROM punch_card_used WHERE biz_type=N'租赁' AND biz_id=18446 AND valid=1);
INSERT INTO punch_card_used (card_id, order_id, biz_type, biz_id, payment_id, punch_count, valid, create_date)
SELECT 13, 64347, N'租赁', 20963, NULL, 1, 1, GETDATE()
WHERE NOT EXISTS (SELECT 1 FROM punch_card_used WHERE biz_type=N'租赁' AND biz_id=20963 AND valid=1);
INSERT INTO punch_card_used (card_id, order_id, biz_type, biz_id, payment_id, punch_count, valid, create_date)
SELECT 21, 65107, N'租赁', 23652, NULL, 1, 1, GETDATE()
WHERE NOT EXISTS (SELECT 1 FROM punch_card_used WHERE biz_type=N'租赁' AND biz_id=23652 AND valid=1);
INSERT INTO punch_card_used (card_id, order_id, biz_type, biz_id, payment_id, punch_count, valid, create_date)
SELECT 29, 68279, N'租赁', 38553, NULL, 1, 1, GETDATE()
WHERE NOT EXISTS (SELECT 1 FROM punch_card_used WHERE biz_type=N'租赁' AND biz_id=38553 AND valid=1);
INSERT INTO punch_card_used (card_id, order_id, biz_type, biz_id, payment_id, punch_count, valid, create_date)
SELECT 29, 68281, N'租赁', 38557, NULL, 1, 1, GETDATE()
WHERE NOT EXISTS (SELECT 1 FROM punch_card_used WHERE biz_type=N'租赁' AND biz_id=38557 AND valid=1);
INSERT INTO punch_card_used (card_id, order_id, biz_type, biz_id, payment_id, punch_count, valid, create_date)
SELECT 30, 68288, N'租赁', 38593, NULL, 1, 1, GETDATE()
WHERE NOT EXISTS (SELECT 1 FROM punch_card_used WHERE biz_type=N'租赁' AND biz_id=38593 AND valid=1);
INSERT INTO punch_card_used (card_id, order_id, biz_type, biz_id, payment_id, punch_count, valid, create_date)
SELECT 30, 68288, N'租赁', 38602, NULL, 1, 1, GETDATE()
WHERE NOT EXISTS (SELECT 1 FROM punch_card_used WHERE biz_type=N'租赁' AND biz_id=38602 AND valid=1);
INSERT INTO punch_card_used (card_id, order_id, biz_type, biz_id, payment_id, punch_count, valid, create_date)
SELECT 31, 68322, N'租赁', 38719, NULL, 1, 1, GETDATE()
WHERE NOT EXISTS (SELECT 1 FROM punch_card_used WHERE biz_type=N'租赁' AND biz_id=38719 AND valid=1);
INSERT INTO punch_card_used (card_id, order_id, biz_type, biz_id, payment_id, punch_count, valid, create_date)
SELECT 31, 68322, N'租赁', 38738, NULL, 1, 1, GETDATE()
WHERE NOT EXISTS (SELECT 1 FROM punch_card_used WHERE biz_type=N'租赁' AND biz_id=38738 AND valid=1);
INSERT INTO punch_card_used (card_id, order_id, biz_type, biz_id, payment_id, punch_count, valid, create_date)
SELECT 29, 68341, N'租赁', 38790, NULL, 1, 1, GETDATE()
WHERE NOT EXISTS (SELECT 1 FROM punch_card_used WHERE biz_type=N'租赁' AND biz_id=38790 AND valid=1);

UPDATE punch_card SET punches = (
    SELECT ISNULL(SUM(u.punch_count), 0) FROM punch_card_used u
    WHERE u.card_id = punch_card.id AND u.valid = 1
  ), update_date = GETDATE()
WHERE id IN (12,13,14,15,21,29,30,31);

COMMIT;
