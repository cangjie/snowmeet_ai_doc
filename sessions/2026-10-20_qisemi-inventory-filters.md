# 七色米库存：正库存、仓库与顶级分类筛选

2026-10-20，Windows 工作区。用户在已上线库存页追加三项条件：默认勾选“只看有库存”、按仓筛选、按顶级商品分类筛选。

## 实现与验证

`SnowmeetApi ai@347209a1`：增加 `Inventory.inStockOnly/topCategoryId` 和 `TopCategories`；顶级分类包含所有有效后代，按 SKU 实际分类取款式。关键词、分类、仓和正库存同时作用后才分页，展开保留全尺码，仓库变更及浏览器历史切换不复用旧仓数量。资源版本 `20261020-stock-filter`。

真实快照测试发现原库存哈希查询在内存紧张时等待 `RESOURCE_SEMAPHORE`；两处库存匹配 SQL 加 `MAX_GRANT_PERCENT=1,MAXDOP 1` 限制资源，未改共享 SQL Server 配置。修正后后端专项 27 项全部通过；客户端 4 项通过；50 模块/96 API 调用的合成页面与四宽度检查通过；本机真实 API/浏览器联调通过。完整 162 模块逐来源遍历是此前基线检查，本轮未重复。

本次核对使用本机已还原的 2026-10-18 完整采集快照：1,103 商品分类节点、59 顶层分类、5,808 SKU、99 仓；全部 5,793 款，有正库存 2,799 款。Fischer RC4 110 MV BOA VAC 26.5 的分类为“【硬件】双板鞋 → Fischer → Fischer 24-25”，分类加旗舰仓组合返回 1 款、3 尺码。数量不代表当前七色米实时库存。

## 交付与边界

- 本机隔离预览仍在 5591，已更新新后端与静态资源；不启动生产 Startup/看门狗，不读生产连接配置。
- 业务分类树清单保存在 `.local/qisemi-category-review-20261020/商品分类完整清单.md`；真实截图、结果 JSON 和测试日志在 `.local/qisemi-stock-filter-20261020/`，均未入 Git。
- 没有新采集、导入、DDL、生产重启或部署操作；本轮没有新增定期任务。企微手机真机尚未验收。
- [接口契约](../docs/qisemi/api-contract.md)、[H5 说明](../docs/qisemi/h5-implementation.md) 和 [筛选说明](../docs/qisemi/inventory-filters-2026-10-20.md) 已同步。
