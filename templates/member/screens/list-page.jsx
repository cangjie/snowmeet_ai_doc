(() => {
// 租赁订单列表页 — 对齐真实系统结构 + 优化
// 保留：① 完整筛选项（店铺/日期/营业/招待/减免/次卡/状态/租赁物/手机/备注/查询）
//       ② 订单行结构：左=订单标签（单/会·散），右=订单具体信息
// 新增：① 查询结果分页
//       ② 日期快捷选择（今天/昨天/本周/上周/本月）

const T = {
  bg: '#f8f9ff', surface: '#ffffff', surfaceLow: '#eff4ff', surface2: '#e5eeff', surface3: '#dce9ff',
  ink: '#0b1c30', ink2: '#3f4850', ink3: '#6f7881', outline: '#bfc7d1',
  primary: '#006495', primaryBright: '#0a85c2', primaryFixed: '#cbe6ff', primaryFixedDim: '#8fcdff',
  success: '#1f8a5b', successBg: '#dff2e7', warn: '#b86e00', warnBg: '#fff1d6',
  danger: '#ba1a1a', dangerBg: '#ffdad6', neutral: '#545f73', neutralBg: '#e6ebf3',
};

// 真实系统的订单状态（来自截图）
const STATUS_MAP = {
  '未开始':   { bg: T.neutralBg, fg: T.neutral, dot: '#8a93a3' },
  '租赁中':   { bg: T.primaryFixed, fg: T.primary, dot: T.primaryBright },
  '部分归还': { bg: '#ffe9c4', fg: '#8b5a00', dot: '#c47f10' },
  '全部归还': { bg: '#dff2e7', fg: T.success, dot: '#34a571' },
  '部分退押金': { bg: '#e9e0ff', fg: '#5b3aa8', dot: '#7a5cd1' },
  '全额退押金': { bg: T.successBg, fg: T.success, dot: '#34a571' },
  '了结关闭': { bg: '#eef0f3', fg: T.ink2, dot: T.ink3 },
  '临时订单': { bg: T.warnBg, fg: T.warn, dot: '#d18900' },
};

const money = (n) => '¥' + Number(n).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// MOCK 订单 ───────────────────────────────────────────────
const ORDERS = [
  { id: 'WT_ZL_260619_00002', status: '租赁中', member: true, name: '苍杰（个人）', gender: '先生',
    phone: '18601197897', date: '2026-06-19', time: '11:13:14', paid: 0.01, payMethod: '支付宝',
    rentTotal: 0, staff: '苍杰（个人）', note: '', biz: '租' },
  { id: 'WT_ZL_260619_00001', status: '租赁中', member: true, name: '苍杰（个人）', gender: '先生',
    phone: '18601197897', date: '2026-06-19', time: '11:03:26', paid: 0.01, payMethod: '微信支付',
    rentTotal: 0, staff: '苍杰（个人）', note: '', biz: '租' },
  { id: 'WT_ZL_260618_00214', status: '全部归还', member: false, name: '王雪琴', gender: '女士',
    phone: '13988218821', date: '2026-06-18', time: '17:42:08', paid: 1699, payMethod: '微信支付',
    rentTotal: 199, staff: '白雪景', note: '雪镜划痕已告知', biz: '租' },
  { id: 'WT_ZL_260618_00207', status: '全额退押金', member: true, name: '蒙先生', gender: '先生',
    phone: '13800010720', date: '2026-06-18', time: '14:22:45', paid: 2110, payMethod: '支付宝',
    rentTotal: 110, staff: '白雪景', note: '', biz: '租' },
  { id: 'WT_ZL_260618_00198', status: '部分退押金', member: true, name: '陈雨桐', gender: '女士',
    phone: '17766556655', date: '2026-06-18', time: '11:30:22', paid: 3568, payMethod: '微信支付',
    rentTotal: 568, staff: '李源', note: '次卡抵扣 2 次', biz: '租' },
  { id: 'WT_ZL_260617_00156', status: '部分归还', member: false, name: '张明轩', gender: '先生',
    phone: '15633093309', date: '2026-06-17', time: '10:08:11', paid: 1799, payMethod: '微信支付',
    rentTotal: 299, staff: '李源', note: '', biz: '租' },
  { id: 'WT_ZL_260617_00142', status: '了结关闭', member: false, name: '黄子博', gender: '先生',
    phone: '13344774477', date: '2026-06-17', time: '09:55:30', paid: 0, payMethod: '—',
    rentTotal: 0, staff: '白雪景', note: '未支付自动关闭', biz: '租' },
  { id: 'WT_ZL_260616_00098', status: '临时订单', member: false, name: '—', gender: '',
    phone: '—', date: '2026-06-16', time: '16:20:50', paid: 0, payMethod: '—',
    rentTotal: 0, staff: '李源', note: '现场散客待确认', biz: '租' },
];

// ── 图标 ──
function MaterialIcon({ name, size = 20, color, fill = 0, weight = 400, style }) {
  return (
    <span className="material-symbols-outlined" style={{ fontSize: size, color, lineHeight: 1, userSelect: 'none',
      fontVariationSettings: `'FILL' ${fill}, 'wght' ${weight}`, ...style }}>{name}</span>
  );
}

// ── 状态 chip ──
function StatusChip({ status, size = 'md' }) {
  const c = STATUS_MAP[status] || STATUS_MAP['租赁中'];
  const dim = size === 'sm';
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: dim ? '3px 8px' : '4px 10px',
      borderRadius: 999, background: c.bg, color: c.fg, fontSize: dim ? 11 : 12, fontWeight: 600, lineHeight: 1, whiteSpace: 'nowrap' }}>
      <span style={{ width: 6, height: 6, borderRadius: 999, background: c.dot }} />{status}
    </span>
  );
}

const BIZ_TAGS = { '零': { bg: '#fde8d2', fg: '#a55a08' }, '租': { bg: T.primaryFixed, fg: T.primary },
  '养': { bg: '#dff2e7', fg: T.success }, '票': { bg: '#fdd9e7', fg: '#a3265c' } };
function BizTag({ k }) {
  const c = BIZ_TAGS[k] || { bg: T.surface2, fg: T.ink2 };
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 18, height: 18,
      borderRadius: 4, background: c.bg, color: c.fg, fontSize: 10.5, fontWeight: 700, lineHeight: 1 }}>{k}</span>
  );
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
      <h1 style={{ fontFamily: 'Lexend, system-ui', fontWeight: 700, fontSize: 17, color: T.primary, margin: 0 }}>租赁订单列表</h1>
      <button style={ghostBtn}><MaterialIcon name="more_horiz" size={22} color={T.primary} /></button>
    </header>
  );
}

// ── 日期工具（以 2026-06-19 为"今天"）──
const TODAY = new Date('2026-06-19T00:00:00');
const fmt = (d) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
function quickRange(key) {
  const d = new Date(TODAY);
  const day = (d.getDay() + 6) % 7; // 周一=0
  if (key === '今天') return [fmt(d), fmt(d)];
  if (key === '昨天') { const y = new Date(d); y.setDate(d.getDate()-1); return [fmt(y), fmt(y)]; }
  if (key === '本周') { const s = new Date(d); s.setDate(d.getDate()-day); return [fmt(s), fmt(d)]; }
  if (key === '上周') { const s = new Date(d); s.setDate(d.getDate()-day-7); const e = new Date(s); e.setDate(s.getDate()+6); return [fmt(s), fmt(e)]; }
  if (key === '本月') { const s = new Date(d.getFullYear(), d.getMonth(), 1); return [fmt(s), fmt(d)]; }
  return [fmt(d), fmt(d)];
}

// ── 分段选择控件（营业/招待/减免/次卡）──
function Segmented({ label, options, value, onChange }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '9px 0' }}>
      <span style={{ fontSize: 13, fontWeight: 600, color: T.ink2, width: 42, flexShrink: 0 }}>{label}</span>
      <div style={{ flex: 1, display: 'flex', background: T.surfaceLow, borderRadius: 9, padding: 3, gap: 3 }}>
        {options.map(opt => {
          const active = value === opt;
          return (
            <button key={opt} onClick={() => onChange(opt)} style={{ flex: 1, height: 32, borderRadius: 7, border: 'none',
              cursor: 'pointer', background: active ? T.surface : 'transparent', color: active ? T.primary : T.ink2,
              fontSize: 13, fontWeight: active ? 700 : 500, fontFamily: 'Lexend',
              boxShadow: active ? '0 1px 2px rgba(0,0,0,0.06)' : 'none' }}>{opt}</button>
          );
        })}
      </div>
    </div>
  );
}

// ── 输入行 ──
function InputRow({ label, children }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '9px 0' }}>
      <span style={{ fontSize: 13, fontWeight: 600, color: T.ink2, width: 42, flexShrink: 0 }}>{label}</span>
      <div style={{ flex: 1, display: 'flex', gap: 8 }}>{children}</div>
    </div>
  );
}
const fieldStyle = { flex: 1, height: 38, borderRadius: 9, border: `1px solid ${T.outline}55`, padding: '0 12px',
  fontSize: 13.5, color: T.ink, fontFamily: 'Lexend', outline: 'none', background: T.surface, minWidth: 0 };

// ── 筛选面板 ──
function FilterPanel({ filter, setFilter, onQuery, open, setOpen }) {
  const set = (patch) => setFilter({ ...filter, ...patch });
  const quickKeys = ['今天', '昨天', '本周', '上周', '本月'];
  const statuses = ['全部', ...Object.keys(STATUS_MAP)];

  return (
    <section style={{ background: T.surface, borderBottom: `1px solid ${T.outline}30` }}>
      {/* 折叠头 */}
      <button onClick={() => setOpen(!open)} style={{ width: '100%', cursor: 'pointer', background: 'transparent',
        border: 'none', padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 8, fontFamily: 'Lexend' }}>
        <MaterialIcon name="filter_alt" size={16} color={T.primary} fill={1} />
        <span style={{ fontSize: 14, fontWeight: 700, color: T.ink }}>筛选条件</span>
        {!open && (
          <span style={{ fontSize: 12, color: T.ink3, marginLeft: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {filter.store} · {filter.dateFrom.slice(5)}~{filter.dateTo.slice(5)} · {filter.status}
          </span>
        )}
        <MaterialIcon name={open ? 'expand_less' : 'expand_more'} size={20} color={T.ink3} style={{ marginLeft: 'auto' }} />
      </button>

      {open && (
        <div style={{ padding: '0 16px 14px' }}>
          {/* 店铺 */}
          <InputRow label="店铺">
            <div style={{ position: 'relative', flex: 1 }}>
              <select value={filter.store} onChange={(e) => set({ store: e.target.value })}
                style={{ ...fieldStyle, width: '100%', appearance: 'none', WebkitAppearance: 'none', cursor: 'pointer', paddingRight: 34 }}>
                {['全部店铺', '崇礼万龙店', '崇礼太舞店', '万龙体验中心'].map(s => <option key={s}>{s}</option>)}
              </select>
              <span style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}>
                <MaterialIcon name="expand_more" size={18} color={T.ink3} />
              </span>
            </div>
          </InputRow>

          {/* 日期 + 快捷 */}
          <div style={{ padding: '9px 0' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: T.ink2, width: 42, flexShrink: 0 }}>日期</span>
              <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 6 }}>
                <input type="date" value={filter.dateFrom} onChange={(e) => set({ dateFrom: e.target.value, quick: '' })} style={{ ...fieldStyle, fontFamily: 'ui-monospace, monospace', fontSize: 12.5 }} />
                <span style={{ color: T.ink3 }}>—</span>
                <input type="date" value={filter.dateTo} onChange={(e) => set({ dateTo: e.target.value, quick: '' })} style={{ ...fieldStyle, fontFamily: 'ui-monospace, monospace', fontSize: 12.5 }} />
              </div>
            </div>
            {/* 快捷日期 */}
            <div style={{ display: 'flex', gap: 6, marginTop: 8, marginLeft: 52, flexWrap: 'wrap' }}>
              {quickKeys.map(k => {
                const active = filter.quick === k;
                return (
                  <button key={k} onClick={() => { const [f, t] = quickRange(k); set({ dateFrom: f, dateTo: t, quick: k }); }}
                    style={{ height: 28, padding: '0 12px', borderRadius: 999, cursor: 'pointer',
                      border: `1px solid ${active ? T.primary : T.outline + '50'}`, background: active ? T.primaryFixed : T.surface,
                      color: active ? T.primary : T.ink2, fontSize: 12.5, fontWeight: active ? 700 : 500, fontFamily: 'Lexend' }}>{k}</button>
                );
              })}
            </div>
          </div>

          <div style={{ borderTop: `1px solid ${T.outline}25`, margin: '4px 0' }} />

          {/* 单选分段组 */}
          <Segmented label="营业" options={['营业', '测试', '全部']} value={filter.biz} onChange={(v) => set({ biz: v })} />
          <Segmented label="招待" options={['正常', '招待', '全部']} value={filter.hospi} onChange={(v) => set({ hospi: v })} />
          <Segmented label="减免" options={['全部', '包含', '不含']} value={filter.exempt} onChange={(v) => set({ exempt: v })} />
          <Segmented label="次卡" options={['全部', '包含', '不含']} value={filter.card} onChange={(v) => set({ card: v })} />

          {/* 状态（chip 多列）*/}
          <div style={{ padding: '9px 0' }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: T.ink2, display: 'block', marginBottom: 8 }}>状态</span>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
              {statuses.map(s => {
                const active = filter.status === s;
                return (
                  <button key={s} onClick={() => set({ status: s })} style={{ height: 30, padding: '0 12px', borderRadius: 999,
                    cursor: 'pointer', border: `1px solid ${active ? T.primary : T.outline + '45'}`,
                    background: active ? T.primary : T.surface, color: active ? '#fff' : T.ink2,
                    fontSize: 12.5, fontWeight: active ? 700 : 500, fontFamily: 'Lexend' }}>{s}</button>
                );
              })}
            </div>
          </div>

          {/* 租赁物 */}
          <InputRow label="租赁物">
            <button style={{ ...fieldStyle, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              cursor: 'pointer', color: T.ink3 }}>
              选择分类 <MaterialIcon name="expand_more" size={16} color={T.ink3} />
            </button>
            <input placeholder="名称或编码" style={fieldStyle} />
          </InputRow>

          {/* 手机 */}
          <InputRow label="手机">
            <input placeholder="输入手机号" style={fieldStyle} />
          </InputRow>

          {/* 备注 */}
          <InputRow label="备注">
            <input placeholder="备注关键字" style={fieldStyle} />
          </InputRow>

          {/* 查询 + 重置 */}
          <div style={{ display: 'flex', gap: 10, marginTop: 12 }}>
            <button onClick={() => setFilter(DEFAULT_FILTER)} style={{ flex: 1, height: 44, borderRadius: 11,
              border: `1px solid ${T.outline}55`, background: T.surface, color: T.ink2, fontSize: 14, fontWeight: 600,
              cursor: 'pointer', fontFamily: 'Lexend' }}>重置</button>
            <button onClick={onQuery} style={{ flex: 2, height: 44, borderRadius: 11, border: 'none', background: T.primary,
              color: '#fff', fontSize: 14, fontWeight: 700, cursor: 'pointer', fontFamily: 'Lexend',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
              <MaterialIcon name="search" size={18} color="#fff" />查询
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

// ── 统计条 ──
function StatsBar({ count, rentTotal }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '12px 16px',
      background: T.surfaceLow, borderBottom: `1px solid ${T.outline}25` }}>
      <span style={{ fontSize: 13, color: T.ink2 }}>总计单数 <b style={{ color: T.primary, fontWeight: 700, fontSize: 16 }}>{count}</b></span>
      <span style={{ width: 1, height: 16, background: T.outline + '50' }} />
      <span style={{ fontSize: 13, color: T.ink2 }}>总计租金 <b style={{ color: T.ink, fontWeight: 700, fontSize: 16 }}>{money(rentTotal)}</b></span>
    </div>
  );
}

// ── 订单行（左标签 + 右信息）──
function TagBox({ text, tone }) {
  const tones = {
    order: { bg: T.primaryFixed, fg: T.primary },
    member: { bg: '#fff1d6', fg: '#9a6a00' },
    guest: { bg: T.neutralBg, fg: T.neutral },
  };
  const c = tones[tone] || tones.order;
  return (
    <div style={{ width: 30, height: 30, borderRadius: 7, background: c.bg, color: c.fg,
      display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 700 }}>{text}</div>
  );
}

function DetailLine({ label, value, value2, label2, mono, accent }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', padding: '3.5px 0', gap: 8 }}>
      <span style={{ fontSize: 12, color: T.ink3, width: 56, flexShrink: 0 }}>{label}</span>
      <span style={{ flex: 1, fontSize: 13, fontWeight: 500, color: accent || T.ink,
        fontFamily: mono ? 'ui-monospace, monospace' : 'Lexend' }}>{value}</span>
      {label2 && <span style={{ fontSize: 12, color: T.ink3, flexShrink: 0 }}>{label2}</span>}
      {value2 && <span style={{ fontSize: 13, fontWeight: 500, color: T.ink, fontFamily: mono ? 'ui-monospace, monospace' : 'Lexend', flexShrink: 0 }}>{value2}</span>}
    </div>
  );
}

function OrderRow({ o, onOpen }) {
  return (
    <div style={{ background: T.surface, borderRadius: 12, border: `1px solid ${T.outline}30`, overflow: 'hidden' }}>
      {/* 头：订单号 + 状态 */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10,
        padding: '11px 14px', background: T.surfaceLow, borderBottom: `1px solid ${T.outline}25` }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: T.ink, fontFamily: 'ui-monospace, monospace', letterSpacing: 0.2 }}>{o.id}</span>
        <StatusChip status={o.status} size="sm" />
      </div>

      {/* 体：左标签 + 右信息 */}
      <div style={{ display: 'flex', gap: 12, padding: '12px 14px' }}>
        {/* 左侧订单标签 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flexShrink: 0 }}>
          <TagBox text={o.biz} tone="order" />
          <TagBox text={o.member ? '会' : '散'} tone={o.member ? 'member' : 'guest'} />
        </div>
        {/* 右侧信息 */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <DetailLine label="日期" value={o.date} label2="时间" value2={o.time} mono />
          <DetailLine label="顾客称呼" value={`${o.name}${o.gender ? ' ' + o.gender : ''}`} />
          <DetailLine label="手机" value={o.phone} mono />
          <DetailLine label="支付金额" value={money(o.paid)} accent={T.primary} label2="方式" value2={o.payMethod} />
          <DetailLine label="总计租金" value={money(o.rentTotal)} />
          <DetailLine label="开单人" value={o.staff} />
          <DetailLine label="备注" value={o.note || '—'} accent={o.note ? T.ink2 : T.ink3} />
        </div>
      </div>

      {/* 底：查看详细 */}
      <div style={{ padding: '0 14px 12px', display: 'flex', justifyContent: 'flex-end' }}>
        <button onClick={onOpen} style={{ height: 36, padding: '0 18px', borderRadius: 9, border: 'none',
          background: T.primary, color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'Lexend',
          display: 'inline-flex', alignItems: 'center', gap: 5 }}>
          查看详细 <MaterialIcon name="chevron_right" size={16} color="#fff" />
        </button>
      </div>
    </div>
  );
}

// ── 分页 ──
function Pagination({ page, totalPages, onChange }) {
  const pages = [];
  for (let i = 1; i <= totalPages; i++) {
    if (i === 1 || i === totalPages || Math.abs(i - page) <= 1) pages.push(i);
    else if (pages[pages.length - 1] !== '…') pages.push('…');
  }
  const Btn = ({ children, disabled, active, onClick, mono = true, w = 32 }) => (
    <button disabled={disabled} onClick={onClick} style={{ minWidth: w, height: 32, padding: '0 8px', borderRadius: 8,
      border: `1px solid ${active ? T.primary : T.outline + '50'}`, background: active ? T.primary : T.surface,
      color: active ? '#fff' : disabled ? T.ink3 + '70' : T.ink, fontSize: 13, fontWeight: active ? 700 : 500,
      fontFamily: mono ? 'ui-monospace, monospace' : 'Lexend', cursor: disabled ? 'not-allowed' : 'pointer',
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>{children}</button>
  );
  return (
    <div style={{ padding: '18px 14px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
      <Btn disabled={page === 1} onClick={() => onChange(page - 1)} mono={false} w={52}>
        <MaterialIcon name="chevron_left" size={16} color={page === 1 ? T.ink3 : T.ink} />上页
      </Btn>
      <div style={{ display: 'flex', gap: 4 }}>
        {pages.map((p, i) => p === '…'
          ? <span key={`g-${i}`} style={{ padding: '0 4px', color: T.ink3, fontSize: 13, alignSelf: 'center' }}>···</span>
          : <Btn key={`p-${p}`} active={p === page} onClick={() => onChange(p)}>{p}</Btn>)}
      </div>
      <Btn disabled={page === totalPages} onClick={() => onChange(page + 1)} mono={false} w={52}>
        下页 <MaterialIcon name="chevron_right" size={16} color={page === totalPages ? T.ink3 : T.ink} />
      </Btn>
    </div>
  );
}

// ── 底部 Tab ──
function BottomNav({ active = '查询' }) {
  const items = [{ k: '工作台', icon: 'dashboard' }, { k: '开单', icon: 'add_circle' },
    { k: '查询', icon: 'search' }, { k: '我的', icon: 'person' }];
  return (
    <nav style={{ position: 'sticky', bottom: 0, zIndex: 20, height: 58, paddingBottom: 4,
      background: 'rgba(255,255,255,0.94)', backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)',
      borderTop: `1px solid ${T.outline}30`, display: 'flex', justifyContent: 'space-around', alignItems: 'center', fontFamily: 'Lexend' }}>
      {items.map(it => {
        const isActive = it.k === active;
        return (
          <button key={it.k} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
            background: 'transparent', border: 'none', cursor: 'pointer', color: isActive ? T.primary : T.ink3 }}>
            <MaterialIcon name={it.icon} size={22} color={isActive ? T.primary : T.ink3} fill={isActive ? 1 : 0} />
            <span style={{ fontSize: 10, fontWeight: isActive ? 600 : 500 }}>{it.k}</span>
          </button>
        );
      })}
    </nav>
  );
}

const DEFAULT_FILTER = {
  store: '全部店铺', dateFrom: '2026-06-19', dateTo: '2026-06-19', quick: '今天',
  biz: '营业', hospi: '正常', exempt: '全部', card: '全部', status: '全部',
};

// ── 页面 ──
function ListPage({ onOpenDetail }) {
  const [filter, setFilter] = React.useState(DEFAULT_FILTER);
  const [filterOpen, setFilterOpen] = React.useState(true);
  const [page, setPage] = React.useState(1);

  const filtered = filter.status === '全部' ? ORDERS : ORDERS.filter(o => o.status === filter.status);
  const totalCount = 47;            // 模拟全量结果
  const totalRent = 12860;
  const totalPages = 6;

  const onQuery = () => { setFilterOpen(false); setPage(1); };

  return (
    <div style={{ width: '100%', height: '100%', background: T.bg, color: T.ink, fontFamily: 'Lexend, system-ui',
      display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <AppBar />
      <div style={{ flex: 1, overflowY: 'auto' }}>
        <FilterPanel filter={filter} setFilter={setFilter} onQuery={onQuery} open={filterOpen} setOpen={setFilterOpen} />
        <StatsBar count={totalCount} rentTotal={totalRent} />

        {/* 结果计数 + 排序 */}
        <div style={{ padding: '12px 14px 4px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 12, color: T.ink3 }}>第 {(page-1)*8 + 1}–{Math.min(page*8, totalCount)} 条 / 共 {totalCount} 条</span>
          <button style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: 'transparent', border: 'none',
            color: T.primary, fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'Lexend' }}>
            按时间倒序 <MaterialIcon name="swap_vert" size={14} color={T.primary} />
          </button>
        </div>

        {/* 订单列表 */}
        <div style={{ padding: '8px 14px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          {filtered.map(o => <OrderRow key={o.id} o={o} onOpen={() => onOpenDetail && onOpenDetail(o)} />)}
        </div>

        <Pagination page={page} totalPages={totalPages} onChange={setPage} />
      </div>
      <BottomNav active="查询" />
    </div>
  );
}

window.ListPage = ListPage;
window.SnowmeetTokens = T;
window.SnowmeetStatusMap = STATUS_MAP;
window.SnowmeetBizTags = BIZ_TAGS;
window.SnowmeetMaterialIcon = MaterialIcon;
window.SnowmeetStatusChip = StatusChip;
window.SnowmeetBizTag = BizTag;

})();
