-- 2026-08-14 清洗「已被接受、shared 却仍为 1」的历史券（已由用户在 SSMS 执行，15 行）
--
-- 背景
-- ----
-- 2023 年前的旧转赠流程在对方接受时没有把 ticket.shared 复位成 0，留下一批
-- 「券已经转给别人、shared 却还是 1」的数据，破坏了「shared=1 ⟹ 券在我名下」这个
-- 新代码依赖的不变量（SetTicketToShare 只对自己名下的券置 1，AcceptTicketCore 接受时置 0）。
--
-- 两个后果：
--   1. 原分享人在「已分享」tab 看到这张券显示成"分享中"并给出撤回按钮，点了必然被
--      CancelShare 的归属校验（ticket.member_id != member.id）拒掉，提示"优惠券不存在"；
--   2. 更实际的影响在**当前持有人**：「未使用」tab 会过滤掉 shared==1 的券，
--      他们在券包里根本看不到自己这张券。
--
-- 代码侧同日已修（见 CLAUDE.md 2026-08-14 条目）：前端不再拿 shared 反推归属，
-- 改由后端 GetMySharedTickets 下发 Ticket.transferredOut。本 SQL 只是把数据本身的
-- 不变量恢复回来——注意光洗数据不够，"对方接受后又转赠给第三人"同样会产生
-- 「券不是我的、shared 却是 1」，那种情况只有代码修复能兜住。
--
-- 命中口径
-- --------
-- shared=1 且在「最后一次分享时刻(shared_time)之后」已存在一条真实转赠接受记录
-- （accepter 非空且 != sender，后者用于排除旧系统"发券给本人"的伪日志，
--   memo 形如"养护订单获得，ID:xxx"/"体验订单获得"/"test"，全库 57 条）
-- => 那次分享早已被消费掉，shared 本应为 0。
--
-- 只改 shared，保留 shared_time：它是"最后一次分享时间"的历史痕迹，
-- GetMySharedTickets 还用它排序；而「已分享」列表是按 ticket_log 推导的、不看 shared，
-- 所以清洗后这些券仍会正常出现在原分享人的「已分享」列表里（显示"对方已接受"）。

UPDATE t SET t.shared = 0
FROM ticket t
WHERE t.valid = 1 AND t.shared = 1 AND t.shared_time IS NOT NULL
  AND EXISTS (SELECT 1 FROM ticket_log l
              WHERE l.code = t.code
                AND LTRIM(RTRIM(l.accepter_open_id)) <> ''
                AND LTRIM(RTRIM(l.accepter_open_id)) <> LTRIM(RTRIM(l.sender_open_id))
                AND l.transact_time >= t.shared_time);

-- 执行结果：15 行；全库 shared=1 AND valid=1 由 94 张降至 79 张。
-- 执行前这 15 张的 shared 全部为 1、shared_time 均非空且执行后原样保留。

-- ---------------------------------------------------------------------------
-- 回滚（把这 15 张的 shared 还原成执行前的 1）
-- ---------------------------------------------------------------------------
-- UPDATE ticket SET shared = 1 WHERE code IN (
--   '043251648',  -- member_id=19323 used=1 shared_time=2025-01-19 13:57:41
--   '150961965',  -- member_id=18872 used=0 shared_time=2025-01-12 14:50:38
--   '157711968',  -- member_id=18016 used=1 shared_time=2025-03-08 15:48:21
--   '259404319',  -- member_id=11386 used=0 shared_time=2023-03-26 20:02:37（本次报障那张）
--   '356668552',  -- member_id=19452 used=1 shared_time=2025-01-21 16:08:31
--   '357905465',  -- member_id=3944  used=0 shared_time=2023-02-24 15:48:37
--   '497752840',  -- member_id=17776 used=1 shared_time=2024-12-28 13:25:13
--   '517052790',  -- member_id=15506 used=1 shared_time=2023-09-27 17:23:51
--   '579556918',  -- member_id=17317 used=1 shared_time=2024-12-21 15:57:12
--   '736459924',  -- member_id=4670  used=1 shared_time=2025-01-16 10:54:18
--   '739514256',  -- member_id=16847 used=1 shared_time=2024-12-14 13:46:38
--   '805347714',  -- member_id=21789 used=0 shared_time=2025-02-18 14:43:59
--   '843462274',  -- member_id=9377  used=0 shared_time=2023-02-23 13:06:40
--   '912085015',  -- member_id=17246 used=1 shared_time=2024-12-21 11:12:23
--   '944881985'   -- member_id=19158 used=1 shared_time=2025-01-17 16:44:33
-- );

-- ---------------------------------------------------------------------------
-- 未处理、也不需要处理的：member_id 为 NULL 的孤儿券
-- ---------------------------------------------------------------------------
-- 全库 member_id IS NULL AND valid=1 的券 3142 张，其中 shared=1 的 54 张。
-- 这批券按 member_id 判归属时不属于任何人，CancelShare 对**任何人**都会拒绝；
-- 但它们同样进不了任何人的券包（GetMyTickets 按 member_id 查），平时不可见，
-- 且落在可转赠白名单(template 12/16)里的是 0 张、不可能被重新分享出去，
-- 因此没有实际影响，不动。
-- 典型样本 089489099 / 958672472：2022 年测试数据，open_id 是
-- 'oHdTn5Wlwy37YA6kmJP6zE9AoTlI_1'（带 _1 后缀，全库这种 49 张，像是旧系统解绑痕迹），
-- 与真实 openid 不相等，member_id 从未写入。它们此前会出现在「已分享」列表纯粹是因为
-- 被"发券给本人"的伪转赠日志捞了进去，代码侧加上 accepter != sender 过滤后已消失。
