-- 2026-05-31 给 shop_list 加 beacon_mac + beacon_uuid 字段
-- 业务：开单界面 shop_selector 通过 BLE/iBeacon 自动选店
-- iOS BLE 扫描拿不到真 MAC（系统伪 UUID），必须用 CoreLocation 走 UUID 路径
-- 所以两字段并存：Android 命中 mac，iOS 命中 uuid

ALTER TABLE shop_list
  ADD beacon_mac NVARCHAR(32) NULL,
      beacon_uuid NVARCHAR(48) NULL;
