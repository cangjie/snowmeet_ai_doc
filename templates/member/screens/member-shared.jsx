// 会员管理 — 共享基础：设计令牌（强调色可换）/ 图标 / 模拟数据 / 通用零件
// 复用易龙雪聚（snowmeet）订单系统的 Material You 调色板与 Lexend + Material Symbols 体系。
// 所有原子组件通过 MemberCtx 读取 T（令牌）与 opts（Tweaks 选项），强调色切换即可全局生效。
(() => {

// ── 调色板（与订单系统一致；强调色相关的 4 档由 makeTokens 派生） ──
const PALETTE = {
  bg: '#f8f9ff', surface: '#ffffff', surfaceLow: '#eff4ff', surface2: '#e5eeff', surface3: '#dce9ff',
  ink: '#0b1c30', ink2: '#3f4850', ink3: '#6f7881', outline: '#bfc7d1',
  success: '#1f8a5b', successBg: '#dff2e7', warn: '#b86e00', warnBg: '#fff1d6',
  danger: '#ba1a1a', dangerBg: '#ffdad6', neutral: '#545f73', neutralBg: '#e6ebf3',
  violet: '#5b3aa8', violetBg: '#e9e0ff',
};

const hexToRgb = (h) => { h = h.replace('#', ''); if (h.length === 3) h = h.replace(/./g, (c) => c + c); const n = parseInt(h, 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; };
const mix = (hex, target, r) => { const a = hexToRgb(hex), b = hexToRgb(target); return '#' + a.map((v, i) => Math.round(v + (b[i] - v) * r).toString(16).padStart(2, '0')).join(''); };

// 由强调色派生完整令牌；保持订单系统的语义层级
function makeTokens(accent) {
  return {
    ...PALETTE,
    primary: accent,
    primaryBright: mix(accent, '#ffffff', 0.16),
    primaryFixed: mix(accent, '#ffffff', 0.84),
    primaryFixedDim: mix(accent, '#ffffff', 0.60),
    accentSoft: mix(accent, '#ffffff', 0.92),
  };
}

const ACCENTS = ['#006495', '#0a7d86', '#3f5bd0', '#1f7a52']; // 雪聚蓝 / 极地青 / 群青 / 雪松绿
const DEFAULT_OPTS = { accent: '#006495', density: 'comfy', storedValueMode: 'split', showMemberId: false, tagStyle: 'filled' };

const MemberCtx = React.createContext({ T: makeTokens('#006495'), opts: DEFAULT_OPTS });
const useMember = () => React.useContext(MemberCtx);

// ── 图标 ──
function MIcon({ name, size = 20, color, fill = 0, weight = 400, style }) {
  return (
    <span className="material-symbols-outlined" style={{ fontSize: size, color, lineHeight: 1, userSelect: 'none',
      fontVariationSettings: `'FILL' ${fill}, 'wght' ${weight}`, ...style }}>{name}</span>
  );
}

const money = (n) => '¥' + Number(n).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const moneyK = (n) => '¥' + Number(n).toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
const num = (n) => Number(n).toLocaleString('zh-CN');

// ── 系统标签：按参与业务自动生成，不可编辑（固定语义色） ──
const SYS_TAGS = {
  '租赁':   { bg: '#cbe6ff', fg: '#0a5d8c', short: '租' },
  '养护':   { bg: '#dff2e7', fg: '#1f8a5b', short: '养' },
  '零售':   { bg: '#fde8d2', fg: '#a55a08', short: '零' },
  '雪票':   { bg: '#fdd9e7', fg: '#a3265c', short: '票' },
  '二手回收': { bg: '#cdeeec', fg: '#0a6b6e', short: '收' },
  '水吧餐厅': { bg: '#efe1cf', fg: '#7c5230', short: '餐' },
  '其他':   { bg: '#e6ebf3', fg: '#545f73', short: '他' },
};

// ── 自定义标签预设库（详情页 / 编辑弹层共用） ──
const PRESET_TAGS = [
  { group: '客户价值', items: ['VIP', '高净值', '老客户', '潜在客户'] },
  { group: '服务关系', items: ['教练', '团体客户', '需回访', '投诉记录', '黑名单'] },
  { group: '偏好', items: ['双板', '单板', '装备控', '亲子'] },
];

// ── 模拟会员数据 ──（以 2026-06-19 为"今天"）
const MEMBERS = [
  { id: '228476', name: '苍杰', gender: '男', phone: '18601197897', sys: ['租赁', '养护'], custom: ['VIP', '教练'],
    sv: { a: 1280, b: 300, c: 180 }, points: 3200, reg: '2025-12-01', last: '2026-06-18', wechat: '苍杰', alipay: 1 },
  { id: '224560', name: '李娜', gender: '女', phone: '13522008866', sys: ['养护', '水吧餐厅'], custom: ['VIP', '装备控'],
    sv: { a: 3600, b: 800, c: 600 }, points: 8900, reg: '2025-10-05', last: '2026-06-16', wechat: 'Nina', alipay: 2 },
  { id: '222013', name: '徐峰', gender: '男', phone: '13700991122', sys: ['租赁', '养护', '二手回收'], custom: ['高净值', '教练'],
    sv: { a: 4800, b: 1200, c: 1500 }, points: 12400, reg: '2025-09-12', last: '2026-06-18', wechat: '徐峰', alipay: 1 },
  { id: '226901', name: '陈雨桐', gender: '女', phone: '17766556655', sys: ['租赁', '雪票', '水吧餐厅'], custom: ['双板', '需回访'],
    sv: { a: 2400, b: 500, c: 320 }, points: 5600, reg: '2025-11-20', last: '2026-06-18', wechat: '桐桐', alipay: 1 },
  { id: '230155', name: '王雪琴', gender: '女', phone: '13988218821', sys: ['租赁', '零售'], custom: ['老客户'],
    sv: { a: 560, b: 0, c: 0 }, points: 860, reg: '2026-01-15', last: '2026-06-18', wechat: '雪琴', alipay: 0 },
  { id: '231880', name: '蒙昊', gender: '男', phone: '13800010720', sys: ['租赁', '二手回收'], custom: ['高净值'],
    sv: { a: 0, b: 0, c: 2000 }, points: 1500, reg: '2026-02-03', last: '2026-06-18', wechat: '蒙昊', alipay: 1 },
  { id: '233402', name: '张明轩', gender: '男', phone: '15633093309', sys: ['租赁', '零售', '雪票'], custom: ['团体客户'],
    sv: { a: 800, b: 120, c: 0 }, points: 2100, reg: '2026-03-10', last: '2026-06-17', wechat: '明轩', alipay: 0 },
  { id: '230988', name: '周敏', gender: '女', phone: '15912345678', sys: ['零售', '雪票', '水吧餐厅'], custom: ['老客户', '需回访'],
    sv: { a: 1020, b: 200, c: 0 }, points: 1760, reg: '2026-01-28', last: '2026-06-15', wechat: '周敏', alipay: 1 },
  { id: '240117', name: '黄子博', gender: '男', phone: '13344774477', sys: ['零售'], custom: [],
    sv: { a: 200, b: 0, c: 0 }, points: 320, reg: '2026-05-22', last: '2026-06-17', wechat: '子博', alipay: 0 },
  { id: '237744', name: '肖志强', gender: '男', phone: '18607197853', sys: ['租赁', '其他'], custom: [],
    sv: { a: 150, b: 0, c: 0 }, points: 540, reg: '2026-04-18', last: '2026-06-16', wechat: '志强', alipay: 0 },
];
const svTotal = (sv) => sv.a + sv.b + sv.c;

// ── 头像（姓名首字母，按性别着色） ──
function Avatar({ name, gender, size = 40 }) {
  const { T } = useMember();
  const female = gender === '女';
  const bg = female ? '#fde4ee' : T.primaryFixed;
  const fg = female ? '#b03a6e' : T.primary;
  return (
    <div style={{ width: size, height: size, borderRadius: 999, background: bg, color: fg, flexShrink: 0,
      display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700,
      fontSize: size * 0.42, fontFamily: 'Lexend' }}>{name[0]}</div>
  );
}

// ── 性别 chip ──
function GenderChip({ gender }) {
  const female = gender === '女';
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 2, padding: '1px 6px 1px 4px', borderRadius: 999,
      background: female ? '#fde4ee' : '#dceaff', color: female ? '#b03a6e' : '#0a5d8c',
      fontSize: 11, fontWeight: 600, lineHeight: 1.6 }}>
      <MIcon name={female ? 'female' : 'male'} size={12} color={female ? '#b03a6e' : '#0a5d8c'} />{gender}
    </span>
  );
}

// ── 系统标签 chip（不可编辑） ──
function SystemTagChip({ name, dense }) {
  const { opts } = useMember();
  const c = SYS_TAGS[name] || SYS_TAGS['其他'];
  const outline = opts.tagStyle === 'outline';
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', padding: dense ? '2px 7px' : '3px 9px', borderRadius: 7,
      background: outline ? 'transparent' : c.bg, color: c.fg,
      border: outline ? `1px solid ${c.fg}40` : '1px solid transparent',
      fontSize: dense ? 11 : 11.5, fontWeight: 600, lineHeight: 1.4, whiteSpace: 'nowrap' }}>{name}</span>
  );
}

// ── 自定义标签 chip（可带删除） ──
function CustomTagChip({ name, dense, onRemove }) {
  const { T, opts } = useMember();
  const outline = opts.tagStyle === 'outline';
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: dense ? '2px 7px' : '3px 9px',
      borderRadius: 7, background: outline ? 'transparent' : T.surface2, color: T.ink2,
      border: outline ? `1px solid ${T.outline}` : '1px solid transparent',
      fontSize: dense ? 11 : 11.5, fontWeight: 600, lineHeight: 1.4, whiteSpace: 'nowrap' }}>
      {name}
      {onRemove && (
        <button onClick={onRemove} style={{ display: 'inline-flex', border: 'none', background: 'transparent',
          padding: 0, margin: '0 -2px 0 0', cursor: 'pointer' }}>
          <MIcon name="close" size={13} color={T.ink3} />
        </button>
      )}
    </span>
  );
}

// ── AppBar ──
function AppBar({ title, onBack, right }) {
  const { T } = useMember();
  const ghost = { width: 36, height: 36, borderRadius: 10, border: 'none', background: 'transparent',
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' };
  return (
    <header style={{ height: 52, background: T.surface, borderBottom: `1px solid ${T.outline}40`, flexShrink: 0,
      display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 12px',
      position: 'sticky', top: 0, zIndex: 30 }}>
      <button onClick={onBack} style={ghost}>
        <MIcon name={onBack ? 'arrow_back_ios_new' : 'menu'} size={onBack ? 20 : 22} color={T.primary} />
      </button>
      <h1 style={{ fontFamily: 'Lexend, system-ui', fontWeight: 700, fontSize: 17, color: T.primary, margin: 0 }}>{title}</h1>
      <div style={{ minWidth: 36, display: 'flex', justifyContent: 'flex-end' }}>
        {right || <button style={ghost}><MIcon name="more_horiz" size={22} color={T.primary} /></button>}
      </div>
    </header>
  );
}

// ── 底部 Tab（与订单系统统一的应用外壳） ──
function BottomNav({ active = '会员' }) {
  const { T } = useMember();
  const items = [{ k: '工作台', icon: 'dashboard' }, { k: '会员', icon: 'group' },
    { k: '开单', icon: 'add_circle' }, { k: '我的', icon: 'person' }];
  return (
    <nav style={{ flexShrink: 0, height: 58, paddingBottom: 4,
      background: 'rgba(255,255,255,0.94)', backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)',
      borderTop: `1px solid ${T.outline}30`, display: 'flex', justifyContent: 'space-around', alignItems: 'center', fontFamily: 'Lexend' }}>
      {items.map((it) => {
        const on = it.k === active;
        return (
          <button key={it.k} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
            background: 'transparent', border: 'none', cursor: 'pointer', color: on ? T.primary : T.ink3 }}>
            <MIcon name={it.icon} size={22} color={on ? T.primary : T.ink3} fill={on ? 1 : 0} />
            <span style={{ fontSize: 10, fontWeight: on ? 600 : 500 }}>{it.k}</span>
          </button>
        );
      })}
    </nav>
  );
}

// ── 可折叠分区（详情页用） ──
function Collapsible({ title, icon, defaultOpen = true, summary, right, children }) {
  const { T } = useMember();
  const [open, setOpen] = React.useState(defaultOpen);
  return (
    <section style={{ margin: '12px 12px 0', borderRadius: 12, background: T.surface,
      border: `1px solid ${T.outline}30`, overflow: 'hidden' }}>
      <div role="button" tabIndex={0} onClick={() => setOpen(!open)} style={{ width: '100%', textAlign: 'left', cursor: 'pointer',
        padding: '13px 16px',
        display: 'flex', alignItems: 'center', gap: 8, fontFamily: 'Lexend, system-ui' }}>
        {icon && <MIcon name={icon} size={16} color={T.primary} />}
        <span style={{ fontSize: 14, fontWeight: 700, color: T.ink }}>{title}</span>
        {!open && summary && <span style={{ fontSize: 12, color: T.ink3, marginLeft: 4, overflow: 'hidden',
          textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{summary}</span>}
        <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
          {right}
          <MIcon name={open ? 'expand_less' : 'expand_more'} size={20} color={T.ink3} />
        </span>
      </div>
      {open && <div style={{ padding: '0 16px 14px' }}>{children}</div>}
    </section>
  );
}

Object.assign(window, {
  MemberMakeTokens: makeTokens, MemberCtx, useMember, MemberAccents: ACCENTS, MemberDefaultOpts: DEFAULT_OPTS,
  MIcon, mmoney: money, mmoneyK: moneyK, mnum: num,
  SYS_TAGS, PRESET_TAGS, MEMBERS, svTotal,
  Avatar, GenderChip, SystemTagChip, CustomTagChip, AppBar, BottomNav, Collapsible,
});

})();
