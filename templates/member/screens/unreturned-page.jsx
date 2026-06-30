// 未归还租赁物列表页
// 结构：店铺筛选 + 模糊搜索（编码/名称/分类）→ 分类分块 → 订单分块 → 租赁物信息
// 规则：① 按店铺筛选 ② 编码/名称/分类名称模糊匹配
//       ③ 分类 → 订单 → 租赁物 三级分块 ④ 每个分类下租赁物按发放时间正序
//       ⑤ 订单显示顾客姓名+电话 ⑥ 租赁物显示发放时间 + 已租天数
(() => {

const T = window.SnowmeetTokens;
const MaterialIcon = window.SnowmeetMaterialIcon;

// 以 2026-06-22 为"今天"计算已租天数
const NOW = new Date('2026-06-22T11:55:00');
const daysSince = (dateStr) => {
  const d = new Date(dateStr.replace(' ', 'T'));
  return Math.max(1, Math.ceil((NOW - d) / 86400000));
};

// ── 数据：分类 → 订单 → 租赁物 ──────────────────────
// 每件租赁物含 发放时间 issueAt（用于正序）
const CATEGORIES = [
  {
    cat: '【其他】雪杖', count: 4, store: '崇礼万龙店',
    orders: [
      { orderId: 'WT_ZL_260618_00214', name: '王雪琴', gender: '女士', phone: '13988218821',
        items: [
          { name: '雪杖 A12', code: 'XZ-0012', issueAt: '2026-06-18 09:42' },
          { name: '雪杖 A15', code: 'XZ-0015', issueAt: '2026-06-18 09:42' },
        ] },
      { orderId: 'WT_ZL_260619_00002', name: '苍杰', gender: '先生', phone: '18601197897',
        items: [
          { name: '雪杖 B03', code: 'XZ-0103', issueAt: '2026-06-19 11:13' },
          { name: '雪杖 B07', code: 'XZ-0107', issueAt: '2026-06-20 10:05' },
        ] },
    ],
  },
  {
    cat: '头盔', count: 3, store: '万龙体验中心',
    orders: [
      { orderId: 'WT_TY_260614_00001', name: '苍杰', gender: '先生', phone: '18601197897',
        items: [{ name: '头盔 100', code: '无编码', issueAt: '2026-06-14 10:11' }] },
      { orderId: 'WT_ZL_260617_00156', name: '张明轩', gender: '先生', phone: '15633093309',
        items: [
          { name: '头盔 088', code: 'TK-0088', issueAt: '2026-06-17 10:08' },
          { name: '头盔 091', code: 'TK-0091', issueAt: '2026-06-21 14:30' },
        ] },
    ],
  },
  {
    cat: '【成人高端】Burton', count: 2, store: '崇礼万龙店',
    orders: [
      { orderId: 'WT_ZL_260618_00198', name: '陈雨桐', gender: '女士', phone: '17766556655',
        items: [
          { name: 'Burton 雪板 045', code: 'SNW-0045', issueAt: '2026-06-18 11:30' },
          { name: 'Burton 雪板 052', code: 'SNW-0052', issueAt: '2026-06-19 16:22' },
        ] },
    ],
  },
  {
    cat: '【双板鞋】全品牌', count: 2, store: '崇礼太舞店',
    orders: [
      { orderId: 'WT_ZL_260616_00098', name: '肖志强', gender: '先生', phone: '18607197853',
        items: [{ name: '双板鞋 212', code: 'SNW-0212', issueAt: '2026-06-16 16:20' }] },
      { orderId: 'WT_ZL_260620_00033', name: '黄子博', gender: '先生', phone: '13344774477',
        items: [{ name: '双板鞋 233', code: 'SNW-0233', issueAt: '2026-06-20 09:15' }] },
    ],
  },
  {
    cat: '雪镜', count: 1, store: '崇礼万龙店',
    orders: [
      { orderId: 'WT_ZL_260621_00071', name: '蒙先生', gender: '先生', phone: '13800010720',
        items: [{ name: '雪镜 X9', code: 'XJ-0009', issueAt: '2026-06-21 13:05' }] },
    ],
  },
];

// 把分类内所有租赁物（跨订单）按发放时间正序，并保留所属订单引用
function sortedOrders(cat) {
  // 收集 (order, item) 对，按 item.issueAt 正序
  const pairs = [];
  cat.orders.forEach(o => o.items.forEach(it => pairs.push({ o, it })));
  pairs.sort((a, b) => a.it.issueAt.localeCompare(b.it.issueAt));
  // 重新按订单分组（保持首次出现顺序 = 时间正序）
  const map = new Map();
  pairs.forEach(({ o, it }) => {
    if (!map.has(o.orderId)) map.set(o.orderId, { ...o, items: [] });
    map.get(o.orderId).items.push(it);
  });
  return [...map.values()];
}

// ── AppBar ──
const ghostBtn = { width: 36, height: 36, borderRadius: 10, border: 'none', background: 'transparent',
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' };
function AppBar() {
  return (
    <header style={{ height: 52, background: T.surface, borderBottom: `1px solid ${T.outline}40`,
      display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 12px',
      position: 'sticky', top: 0, zIndex: 30 }}>
      <button style={ghostBtn}><MaterialIcon name="arrow_back_ios_new" size={20} color={T.primary} /></button>
      <h1 style={{ fontFamily: 'Lexend, system-ui', fontWeight: 700, fontSize: 17, color: T.primary, margin: 0 }}>未归还租赁物</h1>
      <button style={ghostBtn}><MaterialIcon name="more_horiz" size={22} color={T.primary} /></button>
    </header>
  );
}

// ── 筛选区：店铺 + 模糊搜索 ──
function FilterBar({ store, setStore, kw, setKw, onQuery }) {
  const stores = ['全部店铺', '崇礼万龙店', '崇礼太舞店', '万龙体验中心'];
  return (
    <div style={{ background: T.surface, borderBottom: `1px solid ${T.outline}30`, padding: '12px 16px',
      display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* 店铺 + 查询 */}
      <div style={{ display: 'flex', gap: 10 }}>
        <div style={{ position: 'relative', flex: 1 }}>
          <select value={store} onChange={(e) => setStore(e.target.value)}
            style={{ width: '100%', height: 40, borderRadius: 9, border: `1px solid ${T.outline}55`,
              padding: '0 34px 0 12px', fontSize: 14, color: T.ink, fontFamily: 'Lexend', outline: 'none',
              background: T.surface, appearance: 'none', WebkitAppearance: 'none', cursor: 'pointer' }}>
            {stores.map(s => <option key={s}>{s}</option>)}
          </select>
          <span style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}>
            <MaterialIcon name="expand_more" size={18} color={T.ink3} />
          </span>
        </div>
        <button onClick={onQuery} style={{ height: 40, padding: '0 22px', borderRadius: 9, border: 'none',
          background: T.primary, color: '#fff', fontSize: 14, fontWeight: 700, cursor: 'pointer', fontFamily: 'Lexend',
          display: 'inline-flex', alignItems: 'center', gap: 5, flexShrink: 0 }}>
          <MaterialIcon name="search" size={18} color="#fff" />查询
        </button>
      </div>
      {/* 模糊搜索 */}
      <div style={{ position: 'relative' }}>
        <span style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}>
          <MaterialIcon name="search" size={17} color={T.ink3} />
        </span>
        <input value={kw} onChange={(e) => setKw(e.target.value)} placeholder="按编码 / 名称 / 分类模糊搜索"
          style={{ width: '100%', height: 40, borderRadius: 9, border: `1px solid ${T.outline}55`,
            padding: '0 12px 0 38px', fontSize: 13.5, color: T.ink, fontFamily: 'Lexend', outline: 'none', background: T.surfaceLow }} />
        {kw && (
          <button onClick={() => setKw('')} style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
            ...ghostBtn, width: 28, height: 28 }}>
            <MaterialIcon name="cancel" size={16} color={T.ink3} fill={1} />
          </button>
        )}
      </div>
    </div>
  );
}

// ── 统计条 ──
function StatsBar({ catCount, itemCount }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '11px 16px',
      background: T.surfaceLow, borderBottom: `1px solid ${T.outline}25` }}>
      <span style={{ fontSize: 13, color: T.ink2 }}>未归还分类 <b style={{ color: T.primary, fontWeight: 700, fontSize: 16 }}>{catCount}</b></span>
      <span style={{ width: 1, height: 16, background: T.outline + '50' }} />
      <span style={{ fontSize: 13, color: T.ink2 }}>未归还租赁物 <b style={{ color: T.danger, fontWeight: 700, fontSize: 16 }}>{itemCount}</b> 件</span>
    </div>
  );
}

// ── 租赁物信息行 ──
function ItemLine({ it, idx }) {
  const days = daysSince(it.issueAt);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '9px 0',
      borderTop: idx > 0 ? `1px dashed ${T.outline}35` : 'none' }}>
      <div style={{ width: 30, height: 30, borderRadius: 7, background: T.surface2, flexShrink: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <MaterialIcon name="snowboarding" size={17} color={T.primary} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 13.5, fontWeight: 600, color: T.ink }}>{it.name}</span>
          <span style={{ fontSize: 11, color: T.ink3, fontFamily: 'ui-monospace, monospace' }}>{it.code}</span>
        </div>
        <div style={{ fontSize: 11.5, color: T.ink3, marginTop: 2, display: 'flex', alignItems: 'center', gap: 4 }}>
          <MaterialIcon name="schedule" size={12} color={T.ink3} />
          <span style={{ fontFamily: 'ui-monospace, monospace' }}>{it.issueAt}</span>
          <span>发放</span>
        </div>
      </div>
      {/* 已租天数 */}
      <div style={{ textAlign: 'right', flexShrink: 0 }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, padding: '3px 9px', borderRadius: 999,
          background: days >= 3 ? T.dangerBg : T.warnBg, color: days >= 3 ? T.danger : T.warn,
          fontSize: 12, fontWeight: 700, lineHeight: 1 }}>
          已租 {days} 天
        </span>
      </div>
    </div>
  );
}

// ── 订单分块（嵌在分类内）──
function OrderBlock({ o }) {
  return (
    <div style={{ background: T.surface, borderRadius: 10, border: `1px solid ${T.outline}35`, overflow: 'hidden' }}>
      {/* 订单头：顾客姓名 + 电话 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 12px',
        background: T.surfaceLow, borderBottom: `1px solid ${T.outline}25` }}>
        <MaterialIcon name="person" size={15} color={T.ink2} />
        <span style={{ fontSize: 13.5, fontWeight: 700, color: T.ink }}>{o.name} {o.gender}</span>
        <a href={`tel:${o.phone}`} style={{ fontSize: 12.5, color: T.primary, fontWeight: 600,
          fontFamily: 'ui-monospace, monospace', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 3 }}>
          <MaterialIcon name="call" size={12} color={T.primary} />{o.phone}
        </a>
        <span style={{ marginLeft: 'auto', fontSize: 10.5, color: T.ink3, fontFamily: 'ui-monospace, monospace' }}>{o.orderId.slice(-8)}</span>
      </div>
      {/* 租赁物列表（已按时间正序）*/}
      <div style={{ padding: '2px 12px 6px' }}>
        {o.items.map((it, i) => <ItemLine key={it.code + i} it={it} idx={i} />)}
      </div>
    </div>
  );
}

// ── 分类分块（可折叠）──
function CategoryBlock({ cat, defaultOpen }) {
  const [open, setOpen] = React.useState(defaultOpen);
  const orders = sortedOrders(cat);
  return (
    <section style={{ background: T.surface, borderRadius: 12, border: `1px solid ${T.outline}30`, overflow: 'hidden' }}>
      {/* 分类头 */}
      <button onClick={() => setOpen(!open)} style={{ width: '100%', cursor: 'pointer', background: open ? '#e0f2ff' : T.surface,
        border: 'none', padding: '13px 14px', display: 'flex', alignItems: 'center', gap: 10, fontFamily: 'Lexend',
        transition: 'background .15s' }}>
        <MaterialIcon name="category" size={18} color={T.primary} fill={open ? 1 : 0} />
        <span style={{ flex: 1, textAlign: 'left', fontSize: 14.5, fontWeight: 700, color: T.ink, lineHeight: 1.35 }}>{cat.cat}</span>
        <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', minWidth: 26, height: 22,
          padding: '0 8px', borderRadius: 999, background: T.primary, color: '#fff', fontSize: 12.5, fontWeight: 700 }}>{cat.count}</span>
        <MaterialIcon name={open ? 'expand_less' : 'expand_more'} size={20} color={T.ink3} />
      </button>
      {/* 订单分块列表 */}
      {open && (
        <div style={{ padding: '4px 12px 12px', display: 'flex', flexDirection: 'column', gap: 8,
          borderTop: `1px solid ${T.outline}25` }}>
          {orders.map((o, i) => <OrderBlock key={o.orderId + i} o={o} />)}
        </div>
      )}
    </section>
  );
}

// ── 页面 ──
function UnreturnedPage() {
  const [store, setStore] = React.useState('全部店铺');
  const [kw, setKw] = React.useState('');
  const [query, setQuery] = React.useState({ store: '全部店铺', kw: '' });

  const onQuery = () => setQuery({ store, kw });

  // 筛选：店铺 + 模糊（分类名 / 租赁物名 / 编码）
  const filtered = CATEGORIES.filter(cat => {
    if (query.store !== '全部店铺' && cat.store !== query.store) return false;
    if (!query.kw.trim()) return true;
    const k = query.kw.trim().toLowerCase();
    if (cat.cat.toLowerCase().includes(k)) return true;
    return cat.orders.some(o => o.items.some(it =>
      it.name.toLowerCase().includes(k) || it.code.toLowerCase().includes(k)));
  });

  const itemCount = filtered.reduce((s, c) => s + c.count, 0);

  return (
    <div style={{ width: '100%', height: '100%', background: T.bg, color: T.ink, fontFamily: 'Lexend, system-ui',
      display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <AppBar />
      <FilterBar store={store} setStore={setStore} kw={kw} setKw={setKw} onQuery={onQuery} />
      <StatsBar catCount={filtered.length} itemCount={itemCount} />
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {filtered.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '60px 20px', color: T.ink3 }}>
            <MaterialIcon name="inventory_2" size={40} color={T.outline} />
            <div style={{ fontSize: 14, marginTop: 10 }}>没有匹配的未归还租赁物</div>
          </div>
        ) : filtered.map((cat, i) => <CategoryBlock key={cat.cat} cat={cat} defaultOpen={i === 0} />)}
        <div style={{ height: 4 }} />
      </div>
    </div>
  );
}

window.UnreturnedPage = UnreturnedPage;

})();
