// 会员详情页 — 资料 + 储值(A/B/C) + 龙珠 + 标签维护 + 绑定账户 + 最近订单 + 远程业务办理
(() => {
const { useMember, MIcon, mmoney, mnum, SYS_TAGS, MEMBERS, svTotal,
  Avatar, GenderChip, SystemTagChip, CustomTagChip, AppBar, Collapsible } = window;

// 储值类型说明（来自 PRD）
const SV_INFO = {
  a: { label: 'A 类储值', scope: '全平台通用', fg: (T) => T.primary, bg: (T) => T.primaryFixed },
  b: { label: 'B 类储值', scope: '服务类 + 指定商品', fg: (T) => T.success, bg: (T) => T.successBg },
  c: { label: 'C 类储值', scope: '仅租赁 / 养护', fg: (T) => T.violet, bg: (T) => T.violetBg },
};

function PointsBadge({ value, size = 14 }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
      <span style={{ width: size, height: size, borderRadius: 999,
        background: 'radial-gradient(circle at 32% 30%, #ffe39a, #e8a020 70%)', boxShadow: 'inset 0 0 0 0.5px rgba(140,80,0,.3)' }} />
      <span style={{ fontSize: size + 5, fontWeight: 700, color: '#9a6a00', fontFamily: 'Lexend' }}>{mnum(value)}</span>
    </span>
  );
}

// ── 顶部资料卡 ──
function HeaderCard({ m }) {
  const { T } = useMember();
  const Cell = ({ label, value, mono }) => (
    <div>
      <div style={{ fontSize: 11, color: T.ink3, marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 13, fontWeight: 600, color: T.ink, fontFamily: mono ? 'ui-monospace, monospace' : 'Lexend' }}>{value}</div>
    </div>
  );
  return (
    <section style={{ margin: '12px 12px 0', borderRadius: 14, background: T.surface, border: `1px solid ${T.outline}30`, padding: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 13 }}>
        <Avatar name={m.name} gender={m.gender} size={54} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 19, fontWeight: 700, color: T.ink }}>{m.name}</span>
            <GenderChip gender={m.gender} />
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, padding: '2px 8px', borderRadius: 999,
              background: '#fff1d6', color: '#9a6a00', fontSize: 11, fontWeight: 700 }}>
              <MIcon name="workspace_premium" size={12} color="#9a6a00" fill={1} />会员
            </span>
          </div>
          <a href={`tel:${m.phone}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, marginTop: 5,
            fontSize: 14, color: T.primary, fontWeight: 600, fontFamily: 'ui-monospace, monospace', textDecoration: 'none' }}>
            <MIcon name="call" size={14} color={T.primary} />{m.phone}
          </a>
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 12px', marginTop: 14,
        paddingTop: 13, borderTop: `1px dashed ${T.outline}50` }}>
        <Cell label="会员 ID" value={m.id} mono />
        <Cell label="账户状态" value={<span style={{ color: T.success }}>● 正常</span>} />
        <Cell label="注册时间" value={m.reg} mono />
        <Cell label="最近消费" value={m.last} mono />
      </div>
    </section>
  );
}

// ── 资产：储值 A/B/C + 龙珠 ──
function AssetsCard({ m }) {
  const { T } = useMember();
  const total = svTotal(m.sv);
  return (
    <Collapsible title="储值与龙珠" icon="account_balance_wallet" summary={`合计 ${mmoney(total)} · 龙珠 ${mnum(m.points)}`}>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', padding: '4px 0 12px' }}>
        <div>
          <div style={{ fontSize: 11.5, color: T.ink3 }}>储值合计</div>
          <div style={{ fontSize: 26, fontWeight: 800, color: T.primary, fontFamily: 'Lexend', lineHeight: 1.1 }}>{mmoney(total)}</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 11.5, color: T.ink3, marginBottom: 2 }}>可用龙珠</div>
          <PointsBadge value={m.points} size={18} />
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        {['a', 'b', 'c'].map((k) => {
          const info = SV_INFO[k];
          return (
            <div key={k} style={{ flex: 1, borderRadius: 10, border: `1px solid ${T.outline}30`, background: T.surfaceLow, padding: '10px 10px 11px' }}>
              <span style={{ display: 'inline-flex', width: 18, height: 18, borderRadius: 5, background: info.bg(T), color: info.fg(T),
                fontSize: 11, fontWeight: 800, alignItems: 'center', justifyContent: 'center' }}>{k.toUpperCase()}</span>
              <div style={{ fontSize: 14.5, fontWeight: 700, color: m.sv[k] > 0 ? T.ink : T.ink3, fontFamily: 'Lexend', marginTop: 7 }}>{mmoney(m.sv[k])}</div>
              <div style={{ fontSize: 10, color: T.ink3, marginTop: 3, lineHeight: 1.35 }}>{info.scope}</div>
            </div>
          );
        })}
      </div>
    </Collapsible>
  );
}

// ── 标签：系统（只读） + 自定义（可维护） ──
function TagsCard({ m, custom, onEdit }) {
  const { T } = useMember();
  return (
    <Collapsible title="标签" icon="sell" right={
      <button onClick={(e) => { e.stopPropagation(); onEdit(); }} style={{ display: 'inline-flex', alignItems: 'center', gap: 3,
        height: 26, padding: '0 10px', borderRadius: 7, border: `1px solid ${T.primary}`, background: T.primaryFixed,
        color: T.primary, fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'Lexend' }}>
        <MIcon name="edit" size={13} color={T.primary} />编辑
      </button>
    }>
      {/* 系统标签 */}
      <div style={{ padding: '6px 0 2px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 8 }}>
          <span style={{ fontSize: 12.5, fontWeight: 600, color: T.ink2 }}>系统标签</span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, fontSize: 11, color: T.ink3 }}>
            <MIcon name="lock" size={12} color={T.ink3} />按参与业务自动生成，不可编辑
          </span>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
          {m.sys.length ? m.sys.map((s) => <SystemTagChip key={s} name={s} />) : <span style={{ fontSize: 12, color: T.ink3 }}>暂无</span>}
        </div>
      </div>
      <div style={{ borderTop: `1px solid ${T.outline}25`, margin: '12px 0 0', paddingTop: 12 }}>
        <div style={{ fontSize: 12.5, fontWeight: 600, color: T.ink2, marginBottom: 8 }}>自定义标签</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
          {custom.map((s) => <CustomTagChip key={s} name={s} />)}
          <button onClick={onEdit} style={{ display: 'inline-flex', alignItems: 'center', gap: 3, padding: '3px 10px',
            borderRadius: 7, border: `1px dashed ${T.outline}`, background: 'transparent', color: T.ink2,
            fontSize: 11.5, fontWeight: 600, cursor: 'pointer', fontFamily: 'Lexend' }}>
            <MIcon name="add" size={13} color={T.ink2} />添加
          </button>
        </div>
      </div>
    </Collapsible>
  );
}

// ── 绑定账户 ──
function AccountsCard({ m }) {
  const { T } = useMember();
  const Row = ({ icon, iconBg, iconFg, title, sub, action, disabled }) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '11px 0' }}>
      <div style={{ width: 34, height: 34, borderRadius: 8, background: iconBg, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
        <MIcon name={icon} size={19} color={iconFg} fill={1} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13.5, fontWeight: 600, color: T.ink }}>{title}</div>
        <div style={{ fontSize: 11.5, color: T.ink3, marginTop: 1 }}>{sub}</div>
      </div>
      <span style={{ fontSize: 12.5, fontWeight: 600, color: disabled ? T.ink3 : T.primary, cursor: disabled ? 'default' : 'pointer' }}>{action}</span>
    </div>
  );
  return (
    <Collapsible title="绑定账户" icon="link" defaultOpen={false} summary={`微信 1 · 支付宝 ${m.alipay}`}>
      <div style={{ paddingTop: 2 }}>
        <Row icon="chat" iconBg="#dff2e7" iconFg="#1f8a5b" title={`微信 · ${m.wechat}`} sub="全权限登录 · 唯一" action="不可解绑" disabled />
        <div style={{ borderTop: `1px solid ${T.outline}22` }} />
        {m.alipay > 0
          ? Array.from({ length: m.alipay }).map((_, i) => (
              <React.Fragment key={i}>
                {i > 0 && <div style={{ borderTop: `1px solid ${T.outline}22` }} />}
                <Row icon="account_balance_wallet" iconBg="#dceaff" iconFg="#0a5d8c" title={`支付宝子账户 ${i + 1}`} sub="仅可使用本子账户资产" action="解绑" />
              </React.Fragment>
            ))
          : <Row icon="account_balance_wallet" iconBg={T.neutralBg} iconFg={T.neutral} title="支付宝" sub="未绑定" action="绑定" />}
        <button style={{ width: '100%', height: 38, marginTop: 8, borderRadius: 9, border: `1px dashed ${T.outline}`,
          background: 'transparent', color: T.ink2, fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'Lexend',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 5 }}>
          <MIcon name="add" size={15} color={T.ink2} />绑定新支付宝账户
        </button>
      </div>
    </Collapsible>
  );
}

// ── 最近订单（按业务，呼应系统标签） ──
function OrdersCard({ m }) {
  const { T } = useMember();
  const seed = parseInt(m.id.slice(-2), 10);
  const rows = m.sys.filter((s) => s !== '其他').slice(0, 4).map((biz, i) => ({
    biz, no: `${biz === '租赁' ? 'ZL' : biz === '养护' ? 'YH' : biz === '零售' ? 'LS' : biz === '雪票' ? 'XP' : 'QT'}_${260610 + ((seed + i) % 9)}_00${(seed + i) % 9}${i}`,
    amount: [199, 580, 1280, 88, 320][(seed + i) % 5], date: `2026-06-${18 - i}`, status: i === 0 ? '进行中' : '已完成',
  }));
  return (
    <Collapsible title="最近订单" icon="receipt_long" defaultOpen={false} summary={`${rows.length} 条`}>
      <div style={{ paddingTop: 2 }}>
        {rows.map((r, i) => {
          const c = SYS_TAGS[r.biz] || SYS_TAGS['其他'];
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 0', borderTop: i > 0 ? `1px solid ${T.outline}22` : 'none' }}>
              <span style={{ display: 'inline-flex', width: 30, height: 30, borderRadius: 8, background: c.bg, color: c.fg,
                fontSize: 13, fontWeight: 700, alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>{c.short}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12.5, fontWeight: 600, color: T.ink, fontFamily: 'ui-monospace, monospace' }}>{r.no}</div>
                <div style={{ fontSize: 11, color: T.ink3, marginTop: 1 }}>{r.biz} · {r.date}</div>
              </div>
              <div style={{ textAlign: 'right', flexShrink: 0 }}>
                <div style={{ fontSize: 13.5, fontWeight: 700, color: T.ink }}>{mmoney(r.amount)}</div>
                <div style={{ fontSize: 10.5, color: r.status === '进行中' ? T.primary : T.success, fontWeight: 600 }}>{r.status}</div>
              </div>
            </div>
          );
        })}
      </div>
    </Collapsible>
  );
}

// ── 底部：远程业务办理 ──
function RemoteBar() {
  const { T } = useMember();
  const ghost = { flex: 1, height: 44, borderRadius: 10, border: `1px solid ${T.outline}55`, background: T.surface,
    color: T.ink, fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'Lexend',
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 5 };
  return (
    <footer style={{ flexShrink: 0, background: T.surface, borderTop: `1px solid ${T.outline}40`, padding: '10px 12px', display: 'flex', gap: 8 }}>
      <button style={ghost}><MIcon name="redeem" size={16} color={T.ink} />发券</button>
      <button style={ghost}><MIcon name="event_available" size={16} color={T.ink} />预约</button>
      <button style={{ flex: 1.6, height: 44, borderRadius: 10, border: 'none', background: T.primary, color: '#fff',
        fontSize: 14, fontWeight: 700, cursor: 'pointer', fontFamily: 'Lexend',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
        <MIcon name="add_card" size={17} color="#fff" fill={1} />充值储值
      </button>
    </footer>
  );
}

// ── 页面 ──
function MemberDetailPage({ member, onBack }) {
  const { T } = useMember();
  const m = member || MEMBERS[0];
  const [custom, setCustom] = React.useState(m.custom);
  const [editing, setEditing] = React.useState(false);
  const Sheet = window.MemberTagSheet;

  return (
    <div style={{ width: '100%', height: '100%', background: T.bg, color: T.ink, fontFamily: 'Lexend, system-ui',
      display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative' }}>
      <AppBar title="会员详情" onBack={onBack} />
      <div style={{ flex: 1, overflowY: 'auto', paddingBottom: 14 }}>
        <HeaderCard m={m} />
        <AssetsCard m={m} />
        <TagsCard m={m} custom={custom} onEdit={() => setEditing(true)} />
        <AccountsCard m={m} />
        <OrdersCard m={m} />
        <div style={{ height: 4 }} />
      </div>
      <RemoteBar />
      {editing && Sheet && (
        <Sheet sys={m.sys} value={custom} onClose={() => setEditing(false)} onSave={(next) => { setCustom(next); setEditing(false); }} />
      )}
    </div>
  );
}

// 独立演示（详情页 artboard）
function MemberDetailDemo() {
  const { T } = useMember();
  return <div style={{ width: '100%', height: '100%', background: T.bg, overflow: 'hidden' }}><MemberDetailPage member={MEMBERS[0]} /></div>;
}

window.MemberDetailPage = MemberDetailPage;
window.MemberDetailDemo = MemberDetailDemo;

})();
