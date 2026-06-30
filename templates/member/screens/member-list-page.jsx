// 会员列表页 — 筛选面板（姓名/手机/性别/系统标签/自定义标签 多条件）+ 紧凑会员行 + 分页
(() => {
const { useMember, MIcon, mmoney, mnum, SYS_TAGS, PRESET_TAGS, MEMBERS, svTotal,
  Avatar, GenderChip, SystemTagChip, CustomTagChip, AppBar, BottomNav } = window;

const ALL_CUSTOM = PRESET_TAGS.flatMap((g) => g.items);

// ── 龙珠（会员积分）小徽标 ──
function PointsBadge({ value, size = 14 }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
      <span style={{ width: size - 4, height: size - 4, borderRadius: 999,
        background: 'radial-gradient(circle at 32% 30%, #ffe39a, #e8a020 70%)',
        boxShadow: 'inset 0 0 0 0.5px rgba(140,80,0,.3)' }} />
      <span style={{ fontSize: size, fontWeight: 700, color: '#9a6a00', fontFamily: 'Lexend' }}>{mnum(value)}</span>
    </span>
  );
}

// ── 字段控件 ──
function Field({ label, children }) {
  const { T } = useMember();
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '9px 0' }}>
      <span style={{ fontSize: 13, fontWeight: 600, color: T.ink2, width: 56, flexShrink: 0 }}>{label}</span>
      <div style={{ flex: 1, display: 'flex', gap: 8, minWidth: 0 }}>{children}</div>
    </div>
  );
}
function useFieldStyle() {
  const { T } = useMember();
  return { flex: 1, height: 38, borderRadius: 9, border: `1px solid ${T.outline}55`, padding: '0 12px',
    fontSize: 13.5, color: T.ink, fontFamily: 'Lexend', outline: 'none', background: T.surface, minWidth: 0 };
}

// ── 性别分段 ──
function GenderSeg({ value, onChange }) {
  const { T } = useMember();
  return (
    <div style={{ flex: 1, display: 'flex', background: T.surfaceLow, borderRadius: 9, padding: 3, gap: 3 }}>
      {['全部', '男', '女'].map((opt) => {
        const on = value === opt;
        return (
          <button key={opt} onClick={() => onChange(opt)} style={{ flex: 1, height: 32, borderRadius: 7, border: 'none',
            cursor: 'pointer', background: on ? T.surface : 'transparent', color: on ? T.primary : T.ink2,
            fontSize: 13, fontWeight: on ? 700 : 500, fontFamily: 'Lexend',
            boxShadow: on ? '0 1px 2px rgba(0,0,0,0.06)' : 'none' }}>{opt}</button>
        );
      })}
    </div>
  );
}

// ── 标签多选 ──
function TagPick({ name, type, active, onToggle }) {
  const { T } = useMember();
  const c = type === 'sys' ? (SYS_TAGS[name] || SYS_TAGS['其他']) : { bg: T.surface2, fg: T.ink2 };
  return (
    <button onClick={onToggle} style={{ height: 30, padding: '0 11px', borderRadius: 999, cursor: 'pointer',
      border: `1px solid ${active ? (type === 'sys' ? c.fg : T.primary) : T.outline + '50'}`,
      background: active ? (type === 'sys' ? c.bg : T.primaryFixed) : T.surface,
      color: active ? (type === 'sys' ? c.fg : T.primary) : T.ink2,
      fontSize: 12.5, fontWeight: active ? 700 : 500, fontFamily: 'Lexend',
      display: 'inline-flex', alignItems: 'center', gap: 4 }}>
      {active && <MIcon name="check" size={13} color={type === 'sys' ? c.fg : T.primary} />}{name}
    </button>
  );
}

const DEFAULT_FILTER = { name: '', phone: '', gender: '全部', sysTags: [], customTags: [] };

// ── 筛选面板（可折叠） ──
function FilterPanel({ filter, setFilter, onQuery, open, setOpen }) {
  const { T } = useMember();
  const fieldStyle = useFieldStyle();
  const set = (patch) => setFilter({ ...filter, ...patch });
  const toggle = (key, v) => set({ [key]: filter[key].includes(v) ? filter[key].filter((x) => x !== v) : [...filter[key], v] });
  const activeCount = (filter.name ? 1 : 0) + (filter.phone ? 1 : 0) + (filter.gender !== '全部' ? 1 : 0)
    + filter.sysTags.length + filter.customTags.length;

  return (
    <section style={{ background: T.surface, borderBottom: `1px solid ${T.outline}30`, flexShrink: 0 }}>
      <button onClick={() => setOpen(!open)} style={{ width: '100%', cursor: 'pointer', background: 'transparent',
        border: 'none', padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 8, fontFamily: 'Lexend' }}>
        <MIcon name="filter_alt" size={16} color={T.primary} fill={1} />
        <span style={{ fontSize: 14, fontWeight: 700, color: T.ink }}>筛选条件</span>
        {activeCount > 0 && (
          <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', minWidth: 18, height: 18,
            padding: '0 5px', borderRadius: 999, background: T.primary, color: '#fff', fontSize: 11, fontWeight: 700 }}>{activeCount}</span>
        )}
        <MIcon name={open ? 'expand_less' : 'expand_more'} size={20} color={T.ink3} style={{ marginLeft: 'auto' }} />
      </button>

      {open && (
        <div style={{ padding: '0 16px 14px' }}>
          <Field label="姓名"><input value={filter.name} onChange={(e) => set({ name: e.target.value })} placeholder="模糊匹配姓名" style={fieldStyle} /></Field>
          <Field label="手机号"><input value={filter.phone} onChange={(e) => set({ phone: e.target.value })} placeholder="模糊匹配手机号" inputMode="numeric" style={{ ...fieldStyle, fontFamily: 'ui-monospace, monospace' }} /></Field>
          <Field label="性别"><GenderSeg value={filter.gender} onChange={(v) => set({ gender: v })} /></Field>

          <div style={{ padding: '9px 0' }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: T.ink2, display: 'flex', alignItems: 'center', gap: 5, marginBottom: 8 }}>
              系统标签 <span style={{ fontSize: 11, fontWeight: 500, color: T.ink3 }}>· 按业务自动生成</span>
            </span>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
              {Object.keys(SYS_TAGS).map((s) => <TagPick key={s} name={s} type="sys" active={filter.sysTags.includes(s)} onToggle={() => toggle('sysTags', s)} />)}
            </div>
          </div>

          <div style={{ padding: '9px 0' }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: T.ink2, display: 'block', marginBottom: 8 }}>自定义标签</span>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
              {ALL_CUSTOM.map((s) => <TagPick key={s} name={s} type="custom" active={filter.customTags.includes(s)} onToggle={() => toggle('customTags', s)} />)}
            </div>
          </div>

          <div style={{ display: 'flex', gap: 10, marginTop: 12 }}>
            <button onClick={() => setFilter(DEFAULT_FILTER)} style={{ flex: 1, height: 44, borderRadius: 11,
              border: `1px solid ${T.outline}55`, background: T.surface, color: T.ink2, fontSize: 14, fontWeight: 600,
              cursor: 'pointer', fontFamily: 'Lexend' }}>重置</button>
            <button onClick={onQuery} style={{ flex: 2, height: 44, borderRadius: 11, border: 'none', background: T.primary,
              color: '#fff', fontSize: 14, fontWeight: 700, cursor: 'pointer', fontFamily: 'Lexend',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
              <MIcon name="search" size={18} color="#fff" />查询
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

// ── 统计条 ──
function StatsBar({ count, totalSv }) {
  const { T } = useMember();
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '11px 16px', flexShrink: 0,
      background: T.surfaceLow, borderBottom: `1px solid ${T.outline}25` }}>
      <span style={{ fontSize: 13, color: T.ink2 }}>会员数 <b style={{ color: T.primary, fontWeight: 700, fontSize: 16 }}>{count}</b></span>
      <span style={{ width: 1, height: 16, background: T.outline + '50' }} />
      <span style={{ fontSize: 13, color: T.ink2 }}>储值合计 <b style={{ color: T.ink, fontWeight: 700, fontSize: 16 }}>{mmoney(totalSv)}</b></span>
    </div>
  );
}

// ── A/B/C 储值分项 ──
function SvBreakdown({ sv }) {
  const { T } = useMember();
  const cells = [
    { k: 'A', v: sv.a, fg: T.primary, bg: T.primaryFixed },
    { k: 'B', v: sv.b, fg: T.success, bg: T.successBg },
    { k: 'C', v: sv.c, fg: T.violet, bg: T.violetBg },
  ];
  return (
    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
      {cells.map((c) => (
        <span key={c.k} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11.5, fontFamily: 'Lexend' }}>
          <span style={{ width: 15, height: 15, borderRadius: 4, background: c.bg, color: c.fg, fontSize: 10, fontWeight: 800,
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>{c.k}</span>
          <span style={{ color: c.v > 0 ? T.ink2 : T.ink3, fontWeight: 600, fontFamily: 'ui-monospace, monospace' }}>{c.v > 0 ? mmoney(c.v) : '—'}</span>
        </span>
      ))}
    </div>
  );
}

// ── 会员行（紧凑卡片） ──
function MemberRow({ m, onOpen }) {
  const { T, opts } = useMember();
  const dense = opts.density === 'compact';
  const total = svTotal(m.sv);
  const pv = { padding: dense ? '10px 13px 9px' : '12px 14px 11px' };
  return (
    <div onClick={() => onOpen(m)} style={{ background: T.surface, borderRadius: 12, border: `1px solid ${T.outline}30`,
      overflow: 'hidden', cursor: 'pointer', transition: 'box-shadow .12s, border-color .12s' }}
      onMouseEnter={(e) => { e.currentTarget.style.boxShadow = '0 2px 10px rgba(0,0,0,0.06)'; e.currentTarget.style.borderColor = T.primaryFixedDim; }}
      onMouseLeave={(e) => { e.currentTarget.style.boxShadow = 'none'; e.currentTarget.style.borderColor = T.outline + '30'; }}>
      {/* 主体 */}
      <div style={{ display: 'flex', gap: 11, alignItems: 'flex-start', ...pv }}>
        <Avatar name={m.name} gender={m.gender} size={dense ? 36 : 40} />
        <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'flex-start', gap: 10 }}>
          {/* 左列：姓名/性别 + 手机 + [会员ID] */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, minWidth: 0 }}>
              <span style={{ fontSize: 15, fontWeight: 700, color: T.ink, whiteSpace: 'nowrap' }}>{m.name}</span>
              <GenderChip gender={m.gender} />
            </div>
            <div style={{ fontSize: 13, color: T.ink2, fontFamily: 'ui-monospace, monospace', letterSpacing: 0.2, marginTop: 3 }}>{m.phone}</div>
            {opts.showMemberId && (
              <div style={{ fontSize: 11, color: T.ink3, marginTop: 3 }}>会员ID <span style={{ fontFamily: 'ui-monospace, monospace', color: T.ink2 }}>{m.id}</span></div>
            )}
          </div>
          {/* 右列：储值合计 + 龙珠 */}
          <div style={{ flexShrink: 0, textAlign: 'right', whiteSpace: 'nowrap' }}>
            <div>
              <span style={{ fontSize: 10.5, color: T.ink3 }}>储值 </span>
              <span style={{ fontSize: 15, fontWeight: 700, color: T.primary, fontFamily: 'Lexend' }}>{mmoney(total)}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 4, marginTop: 4 }}>
              <span style={{ fontSize: 10.5, color: T.ink3 }}>龙珠</span>
              <PointsBadge value={m.points} size={13.5} />
            </div>
          </div>
        </div>
      </div>
      {/* 标签行 */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, padding: dense ? '0 13px 9px' : '0 14px 10px' }}>
        {m.sys.map((s) => <SystemTagChip key={s} name={s} dense={dense} />)}
        {m.custom.map((s) => <CustomTagChip key={s} name={s} dense={dense} />)}
      </div>
      {/* 底部：A/B/C 储值 + 日期 */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10,
        padding: dense ? '8px 13px' : '9px 14px', borderTop: `1px solid ${T.outline}22`, background: T.surfaceLow + '80' }}>
        {opts.storedValueMode === 'split'
          ? <SvBreakdown sv={m.sv} />
          : <span style={{ fontSize: 11.5, color: T.ink3 }}>储值合计 <b style={{ color: T.ink2 }}>{mmoney(total)}</b></span>}
        <span style={{ fontSize: 10.5, color: T.ink3, flexShrink: 0, textAlign: 'right', fontFamily: 'ui-monospace, monospace' }}>
          注册 {m.reg.slice(2)} · 近 {m.last.slice(5)}
        </span>
      </div>
    </div>
  );
}

// ── 分页 ──
function Pagination({ page, totalPages, onChange }) {
  const { T } = useMember();
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
    <div style={{ padding: '16px 14px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
      <Btn disabled={page === 1} onClick={() => onChange(page - 1)} mono={false} w={52}><MIcon name="chevron_left" size={16} color={page === 1 ? T.ink3 : T.ink} />上页</Btn>
      <div style={{ display: 'flex', gap: 4 }}>
        {pages.map((p, i) => p === '…'
          ? <span key={`g-${i}`} style={{ padding: '0 4px', color: T.ink3, fontSize: 13, alignSelf: 'center' }}>···</span>
          : <Btn key={`p-${p}`} active={p === page} onClick={() => onChange(p)}>{p}</Btn>)}
      </div>
      <Btn disabled={page === totalPages} onClick={() => onChange(page + 1)} mono={false} w={52}>下页 <MIcon name="chevron_right" size={16} color={page === totalPages ? T.ink3 : T.ink} /></Btn>
    </div>
  );
}

// ── 模糊筛选 ──
function applyFilter(list, f) {
  return list.filter((m) => {
    if (f.name && !m.name.includes(f.name.trim())) return false;
    if (f.phone && !m.phone.includes(f.phone.trim())) return false;
    if (f.gender !== '全部' && m.gender !== f.gender) return false;
    if (f.sysTags.length && !f.sysTags.every((t) => m.sys.includes(t))) return false;
    if (f.customTags.length && !f.customTags.every((t) => m.custom.includes(t))) return false;
    return true;
  });
}

// ── 页面 ──
function MemberListPage() {
  const { T } = useMember();
  const [filter, setFilter] = React.useState(DEFAULT_FILTER);
  const [filterOpen, setFilterOpen] = React.useState(false);
  const [applied, setApplied] = React.useState(DEFAULT_FILTER);
  const [page, setPage] = React.useState(1);
  const [openMember, setOpenMember] = React.useState(null);

  const results = applyFilter(MEMBERS, applied);
  const totalSv = results.reduce((s, m) => s + svTotal(m.sv), 0);
  const onQuery = () => { setApplied(filter); setFilterOpen(false); setPage(1); };

  const Detail = window.MemberDetailPage;

  return (
    <div style={{ width: '100%', height: '100%', background: T.bg, color: T.ink, fontFamily: 'Lexend, system-ui',
      display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative' }}>
      <AppBar title="会员管理" right={
        <button style={{ width: 36, height: 36, borderRadius: 10, border: 'none', background: 'transparent',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
          <MIcon name="person_add" size={22} color={T.primary} />
        </button>} />
      <div style={{ flex: 1, overflowY: 'auto' }}>
        <FilterPanel filter={filter} setFilter={setFilter} onQuery={onQuery} open={filterOpen} setOpen={setFilterOpen} />
        <StatsBar count={results.length} totalSv={totalSv} />

        <div style={{ padding: '12px 14px 4px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 12, color: T.ink3 }}>共 {results.length} 位会员</span>
          <button style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: 'transparent', border: 'none',
            color: T.primary, fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'Lexend' }}>
            按最近消费 <MIcon name="swap_vert" size={14} color={T.primary} />
          </button>
        </div>

        <div style={{ padding: '8px 14px', display: 'flex', flexDirection: 'column', gap: 11 }}>
          {results.length === 0
            ? <div style={{ textAlign: 'center', padding: '54px 20px', color: T.ink3 }}>
                <MIcon name="person_search" size={40} color={T.outline} />
                <div style={{ fontSize: 14, marginTop: 10 }}>没有匹配的会员</div>
              </div>
            : results.map((m) => <MemberRow key={m.id} m={m} onOpen={setOpenMember} />)}
        </div>

        {results.length > 0 && <Pagination page={page} totalPages={6} onChange={setPage} />}
      </div>
      <BottomNav active="会员" />

      {openMember && Detail && (
        <div style={{ position: 'absolute', inset: 0, zIndex: 100, animation: 'mbSlideIn .22s ease' }}>
          <Detail member={openMember} onBack={() => setOpenMember(null)} />
        </div>
      )}
    </div>
  );
}

window.MemberListPage = MemberListPage;
window.MemberPointsBadge = PointsBadge;
window.MemberSvBreakdown = SvBreakdown;

})();
