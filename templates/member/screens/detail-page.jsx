// 租赁订单明细页 — 对齐真实系统结构
// 本次重点：重新设计「租赁商品费用」与「租赁物数据 + 操作」展示
//   - 商品费用：起租/退租时间块 + 费用明细（小计强调）
//   - 租赁物卡：缩略图 + 名称 + 状态 / 发放·归还时间轴 / 赔偿·备注 / 统一操作条 / 发放记录
//   - 操作不再用彩虹按钮：归还=主操作(蓝)，暂存/更换=次操作(描边)，赔偿=危险描边
(() => {

const T = window.SnowmeetTokens;
const MaterialIcon = window.SnowmeetMaterialIcon;

const money = (n) => '¥' + Number(n).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// ── 数据（对齐截图场景：会员 苍杰 · 头盔单品） ──────────────
const DETAIL = {
  id: 'WT_TY_260614_00001',
  status: '租赁中',
  name: '苍杰', gender: '先生',
  phone: '18601197897',
  member: true,
  memberId: '228476',
  store: '万龙体验中心', staff: '苍杰',
  paid: 230, refund: 0, payCount: 1, refundCount: 0,
  heldDeposit: 200, releasedDeposit: 0,
  payLog: [
    { date: '2026-06-14', time: '10:09:24', method: '微信', type: '支付', amt: 230 },
  ],
  products: [
    {
      kind: '单品',
      name: '头盔',
      unit: '只',
      deposit: 200, rent: 30,
      startDate: '2026-06-14', startTime: '10:09:00',
      endDate: '——', endTime: '——',
      discount: 0, comp: 0, overtime: 0, hospitality: false, subtotal: 30,
      note: '',
      rentDetail: [
        { date: '2026-06-14', rent: 30, discount: 0, subtotal: 30, exempt: false },
      ],
      items: [
        {
          name: '100', renamed: false, code: '无编码',
          cat: '头盔',
          issueDate: '2026-06-14', issueTime: '10:11:00',
          returnDate: '——', returnTime: '——',
          issuer: '苍杰（个人）', receiver: '——',
          status: '已发放', comp: 0, note: '',
          dispatchLog: [
            { date: '2026-06-14', time: '10:11:00', action: '发放', staff: '苍杰（个人）' },
          ],
        },
      ],
    },
  ],
  refundSummary: {
    totalDeposit: 200, totalRent: 30, totalOvertime: 0, totalComp: 0,
    refundableDeposit: 200, refunded: 0, actual: 200,
  },
};

// ── 通用零件 ──────────────────────────────
const btn = { width: 36, height: 36, borderRadius: 10, border: 'none', background: 'transparent',
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' };

function AppBar({ onBack }) {
  return (
    <header style={{ height: 52, background: T.surface, borderBottom: `1px solid ${T.outline}40`,
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '0 12px', position: 'sticky', top: 0, zIndex: 30 }}>
      <button onClick={onBack} style={btn}><MaterialIcon name="arrow_back_ios_new" size={20} color={T.primary} /></button>
      <h1 style={{ fontFamily: 'Lexend, system-ui', fontWeight: 700, fontSize: 17, color: T.primary, margin: 0 }}>租赁订单明细</h1>
      <button style={btn}><MaterialIcon name="more_horiz" size={22} color={T.primary} /></button>
    </header>
  );
}

function Collapsible({ title, icon, defaultOpen = true, summary, children }) {
  const [open, setOpen] = React.useState(defaultOpen);
  return (
    <section style={{ margin: '12px 12px 0', borderRadius: 12, background: T.surface,
      border: `1px solid ${T.outline}30`, overflow: 'hidden' }}>
      <button onClick={() => setOpen(!open)} style={{ width: '100%', textAlign: 'left', cursor: 'pointer',
        background: 'transparent', border: 'none', padding: '13px 16px',
        display: 'flex', alignItems: 'center', gap: 8, fontFamily: 'Lexend, system-ui' }}>
        {icon && <MaterialIcon name={icon} size={16} color={T.primary} />}
        <span style={{ fontSize: 14, fontWeight: 700, color: T.ink }}>{title}</span>
        {!open && summary && <span style={{ fontSize: 12, color: T.ink3, marginLeft: 4 }}>{summary}</span>}
        <MaterialIcon name={open ? 'expand_less' : 'expand_more'} size={20} color={T.ink3} style={{ marginLeft: 'auto' }} />
      </button>
      {open && <div style={{ padding: '0 16px 14px' }}>{children}</div>}
    </section>
  );
}

function Field({ label, value, mono, accent, strong }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '7px 0', gap: 12 }}>
      <span style={{ fontSize: 13, color: T.ink3, flexShrink: 0 }}>{label}</span>
      <span style={{ fontSize: strong ? 14 : 13, fontWeight: strong ? 700 : 500, color: accent || T.ink,
        textAlign: 'right', fontFamily: mono ? 'ui-monospace, SF Mono, monospace' : 'Lexend, system-ui' }}>{value}</span>
    </div>
  );
}

function FieldGrid({ rows }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr auto 1fr', rowGap: 8, columnGap: 10, alignItems: 'center' }}>
      {rows.map((r, i) => (
        <React.Fragment key={i}>
          <span style={{ fontSize: 12.5, color: T.ink3 }}>{r[0]}</span>
          <span style={{ fontSize: 13, fontWeight: 600, color: r.accent0 || T.ink, fontFamily: r.mono ? 'ui-monospace, monospace' : 'Lexend' }}>{r[1]}</span>
          <span style={{ fontSize: 12.5, color: T.ink3 }}>{r[2] || ''}</span>
          <span style={{ fontSize: 13, fontWeight: 600, color: r.accent1 || T.ink, textAlign: 'right', fontFamily: r.mono ? 'ui-monospace, monospace' : 'Lexend' }}>{r[3] || ''}</span>
        </React.Fragment>
      ))}
    </div>
  );
}

// ── 订单信息 ──────────────────────────────
function OrderInfo({ d }) {
  return (
    <Collapsible title="订单信息" icon="receipt_long"
      summary={`${d.name} ${d.gender} · ${d.id}`}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '4px 0 12px' }}>
        <div style={{ width: 42, height: 42, borderRadius: 999, background: T.primaryFixed, color: T.primary,
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 17, fontWeight: 700, flexShrink: 0 }}>
          {d.name[0]}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 16, fontWeight: 700, color: T.ink }}>{d.name} {d.gender}</span>
            {d.member ? (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, padding: '2px 8px', borderRadius: 999,
                background: '#fff1d6', color: '#9a6a00', fontSize: 11, fontWeight: 700, lineHeight: 1 }}>
                <MaterialIcon name="workspace_premium" size={12} color="#9a6a00" fill={1} />会员
              </span>
            ) : (
              <span style={{ padding: '2px 8px', borderRadius: 999, background: T.neutralBg || '#e6ebf3',
                color: T.neutral || '#545f73', fontSize: 11, fontWeight: 700, lineHeight: 1 }}>散客</span>
            )}
          </div>
          <a href={`tel:${d.phone}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, marginTop: 4,
            fontSize: 13, color: T.primary, fontWeight: 600, fontFamily: 'ui-monospace, monospace', textDecoration: 'none' }}>
            <MaterialIcon name="call" size={13} color={T.primary} />{d.phone}
          </a>
        </div>
      </div>
      <div style={{ borderTop: `1px dashed ${T.outline}40`, paddingTop: 4 }}>
        <Field label="订单号" value={d.id} mono />
        <Field label="所属门店" value={d.store} />
        <Field label="开单店员" value={d.staff} />
      </div>
    </Collapsible>
  );
}

// ── 支付信息 ──────────────────────────────
function PaymentInfo({ d }) {
  return (
    <Collapsible title="支付信息" icon="payments"
      summary={`支付 ${money(d.paid)} · 退款 ${money(d.refund)}`}>
      <div style={{ display: 'flex', gap: 10, padding: '4px 0 12px' }}>
        <div style={{ flex: 1, padding: '10px 12px', borderRadius: 10, background: '#e0f2ff' }}>
          <div style={{ fontSize: 11, color: T.primary, fontWeight: 600, marginBottom: 3 }}>支付总金额</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: T.primary, fontFamily: 'Lexend' }}>{money(d.paid)}</div>
        </div>
        <div style={{ flex: 1, padding: '10px 12px', borderRadius: 10, background: T.dangerBg || '#ffdad6' }}>
          <div style={{ fontSize: 11, color: T.danger, fontWeight: 600, marginBottom: 3 }}>退款总金额</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: T.danger, fontFamily: 'Lexend' }}>{money(d.refund)}</div>
        </div>
      </div>
      <FieldGrid rows={[
        ['支付笔数', String(d.payCount), '退款笔数', String(d.refundCount)],
        ['在押押金', money(d.heldDeposit), '解押押金', money(d.releasedDeposit)],
      ]} />
      <div style={{ marginTop: 12, border: `1px solid ${T.outline}30`, borderRadius: 10, overflow: 'hidden' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr 0.8fr 1fr', background: T.surfaceLow,
          padding: '8px 12px', fontSize: 11, fontWeight: 600, color: T.ink3 }}>
          <span>日期 / 时间</span><span>支付方式</span><span>类型</span><span style={{ textAlign: 'right' }}>金额</span>
        </div>
        {d.payLog.map((p, i) => (
          <div key={i} style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr 0.8fr 1fr',
            padding: '9px 12px', fontSize: 12, alignItems: 'center', borderTop: `1px solid ${T.outline}25` }}>
            <span style={{ color: T.ink2, fontFamily: 'ui-monospace, monospace', fontSize: 11 }}>{p.date}<br/>{p.time}</span>
            <span style={{ color: T.ink }}>{p.method}</span>
            <span style={{ color: p.type === '退款' ? T.danger : T.success, fontWeight: 700 }}>{p.type}</span>
            <span style={{ textAlign: 'right', fontWeight: 700, color: p.type === '退款' ? T.danger : T.success }}>{money(p.amt)}</span>
          </div>
        ))}
      </div>
    </Collapsible>
  );
}

// ── 状态 pill ──
function ItemStatusPill({ status }) {
  const map = {
    '已发放': { bg: T.primaryFixed, fg: T.primary }, '已暂存': { bg: '#fff1d6', fg: '#b86e00' },
    '已归还': { bg: '#dff2e7', fg: T.success }, '异店归还': { bg: '#e9e0ff', fg: '#5b3aa8' },
    '已折损': { bg: '#ffdad6', fg: T.danger },
  };
  const c = map[status] || map['已发放'];
  return (
    <span style={{ padding: '3px 9px', borderRadius: 999, background: c.bg, color: c.fg,
      fontSize: 11, fontWeight: 700, lineHeight: 1, whiteSpace: 'nowrap' }}>{status}</span>
  );
}

// ── 费用明细（商品级） ──────────────────────────────
function FeeBreakdown({ p }) {
  const Cell = ({ label, value, danger }) => (
    <div style={{ flex: '1 1 30%', minWidth: 78 }}>
      <div style={{ fontSize: 11, color: T.ink3, marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 13, fontWeight: 600, color: danger && value !== money(0) ? T.danger : T.ink }}>{value}</div>
    </div>
  );
  return (
    <div style={{ border: `1px solid ${T.outline}30`, borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ padding: '11px 12px', display: 'flex', flexWrap: 'wrap', rowGap: 11, columnGap: 6 }}>
        <Cell label="租金" value={money(p.rent)} />
        <Cell label="减免" value={money(p.discount)} danger />
        <Cell label="赔偿" value={money(p.comp)} danger />
        <Cell label="超时" value={money(p.overtime)} />
        <Cell label="招待" value={p.hospitality ? '是' : '否'} />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 12px', background: T.surfaceLow, borderTop: `1px solid ${T.outline}30` }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: T.ink2 }}>小计</span>
        <span style={{ fontSize: 18, fontWeight: 700, color: T.primary, fontFamily: 'Lexend' }}>{money(p.subtotal)}</span>
      </div>
    </div>
  );
}

// 起租/退租 时间块
function RentPeriod({ p }) {
  const Block = ({ label, date, time, active }) => (
    <div style={{ flex: 1, padding: '10px 12px', borderRadius: 10,
      background: active ? '#e0f2ff' : T.surfaceLow, border: `1px solid ${active ? T.primary + '30' : T.outline + '25'}` }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 5 }}>
        <span style={{ width: 7, height: 7, borderRadius: 999, background: active ? T.primary : T.outline }} />
        <span style={{ fontSize: 11, fontWeight: 600, color: active ? T.primary : T.ink3 }}>{label}</span>
      </div>
      <div style={{ fontSize: 13, fontWeight: 600, color: T.ink, fontFamily: 'ui-monospace, monospace' }}>{date}</div>
      <div style={{ fontSize: 12, color: T.ink2, fontFamily: 'ui-monospace, monospace', marginTop: 1 }}>{time}</div>
    </div>
  );
  return (
    <div style={{ display: 'flex', alignItems: 'stretch', gap: 8 }}>
      <Block label="起租" date={p.startDate} time={p.startTime} active />
      <div style={{ display: 'flex', alignItems: 'center', color: T.outline }}>
        <MaterialIcon name="arrow_forward" size={16} color={T.outline} />
      </div>
      <Block label="退租" date={p.endDate} time={p.endTime} />
    </div>
  );
}

// 租金明细（嵌套折叠）
function RentDetail({ rows }) {
  const [open, setOpen] = React.useState(false);
  return (
    <div>
      <button onClick={() => setOpen(!open)} style={{ width: '100%', cursor: 'pointer', background: 'transparent',
        border: 'none', padding: '10px 0', display: 'flex', alignItems: 'center', gap: 6, fontFamily: 'Lexend' }}>
        <MaterialIcon name="receipt" size={15} color={T.primary} />
        <span style={{ fontSize: 13, fontWeight: 600, color: T.ink }}>租金明细</span>
        <span style={{ fontSize: 11, color: T.ink3 }}>{rows.length} 天</span>
        <MaterialIcon name={open ? 'expand_less' : 'expand_more'} size={18} color={T.ink3} style={{ marginLeft: 'auto' }} />
      </button>
      {open && (
        <div style={{ paddingBottom: 10 }}>
          <div style={{ border: `1px solid ${T.outline}30`, borderRadius: 8, overflow: 'hidden' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 1fr 1fr 1fr 0.6fr', background: T.surfaceLow,
              padding: '7px 10px', fontSize: 11, fontWeight: 600, color: T.ink3 }}>
              <span>日期</span><span style={{ textAlign: 'right' }}>租金</span><span style={{ textAlign: 'right' }}>减免</span>
              <span style={{ textAlign: 'right' }}>小计</span><span style={{ textAlign: 'center' }}>免除</span>
            </div>
            {rows.map((r, i) => (
              <div key={i} style={{ display: 'grid', gridTemplateColumns: '1.3fr 1fr 1fr 1fr 0.6fr',
                padding: '8px 10px', fontSize: 12, alignItems: 'center', borderTop: `1px solid ${T.outline}25` }}>
                <span style={{ color: T.ink2, fontFamily: 'ui-monospace, monospace', fontSize: 11 }}>{r.date}</span>
                <span style={{ textAlign: 'right', color: T.ink }}>{r.rent.toFixed(2)}</span>
                <span style={{ textAlign: 'right', color: r.discount > 0 ? T.danger : T.ink3 }}>{r.discount.toFixed(2)}</span>
                <span style={{ textAlign: 'right', fontWeight: 700, color: T.primary }}>{money(r.subtotal)}</span>
                <span style={{ textAlign: 'center' }}>
                  <span style={{ display: 'inline-block', width: 16, height: 16, borderRadius: 4,
                    border: `1.5px solid ${r.exempt ? T.primary : T.outline}`, background: r.exempt ? T.primary : 'transparent' }} />
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── 操作按钮（统一风格，告别彩虹） ──
function ActionBtn({ icon, label, variant = 'ghost', onClick }) {
  const styles = {
    primary: { bg: T.primary, fg: '#fff', bd: 'transparent' },
    ghost:   { bg: T.surface, fg: T.ink,  bd: T.outline + '60' },
    danger:  { bg: T.surface, fg: T.danger, bd: T.danger + '55' },
  }[variant];
  return (
    <button onClick={onClick} style={{ flex: 1, height: 38, borderRadius: 9, cursor: 'pointer',
      background: styles.bg, color: styles.fg, border: `1px solid ${styles.bd}`,
      fontSize: 13, fontWeight: 600, fontFamily: 'Lexend',
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 4 }}>
      {icon && <MaterialIcon name={icon} size={15} color={styles.fg} fill={variant === 'primary' ? 1 : 0} />}
      {label}
    </button>
  );
}

// 发放记录（嵌套折叠时间轴）
function DispatchLog({ rows }) {
  const [open, setOpen] = React.useState(false);
  return (
    <div style={{ borderTop: `1px solid ${T.outline}30` }}>
      <button onClick={() => setOpen(!open)} style={{ width: '100%', cursor: 'pointer', background: 'transparent',
        border: 'none', padding: '10px 0 2px', display: 'flex', alignItems: 'center', gap: 6, fontFamily: 'Lexend' }}>
        <MaterialIcon name="history" size={14} color={T.ink3} />
        <span style={{ fontSize: 12.5, fontWeight: 600, color: T.ink2 }}>发放记录</span>
        <span style={{ fontSize: 11, color: T.ink3 }}>{rows.length}</span>
        <MaterialIcon name={open ? 'expand_less' : 'expand_more'} size={16} color={T.ink3} style={{ marginLeft: 'auto' }} />
      </button>
      {open && (
        <div style={{ padding: '8px 0 6px 4px' }}>
          {rows.map((r, i) => (
            <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', paddingBottom: i < rows.length - 1 ? 10 : 0 }}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 3 }}>
                <span style={{ width: 8, height: 8, borderRadius: 999, background: r.action === '归还' ? T.success : T.primary }} />
                {i < rows.length - 1 && <span style={{ width: 1.5, flex: 1, minHeight: 16, background: T.outline + '50' }} />}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 12.5, fontWeight: 700, color: T.ink }}>{r.action}</span>
                  <span style={{ fontSize: 11, color: T.ink3 }}>{r.staff}</span>
                </div>
                <div style={{ fontSize: 11, color: T.ink3, fontFamily: 'ui-monospace, monospace', marginTop: 1 }}>{r.date} {r.time}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// 单个租赁物卡（重新设计）
function RentalItemCard({ it, onSwap }) {
  // 操作按钮：依状态决定
  const issued = it.status === '已发放' || it.status === '已暂存';
  return (
    <div style={{ background: T.surface, borderRadius: 11, border: `1px solid ${T.outline}40`, overflow: 'hidden' }}>
      {/* 头部：缩略图 + 名称 + 状态 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '11px 12px',
        background: T.surfaceLow, borderBottom: `1px solid ${T.outline}25` }}>
        <div style={{ width: 38, height: 38, borderRadius: 9, background: T.surface,
          border: `1px solid ${T.outline}40`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <MaterialIcon name="sports_motorsports" size={21} color={T.primary} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <span style={{ fontSize: 15, fontWeight: 700, color: T.ink }}>{it.name}</span>
            {it.renamed && <span style={{ fontSize: 10, color: T.ink3, fontWeight: 600,
              background: T.surface3, padding: '1px 5px', borderRadius: 4 }}>更名</span>}
            <ItemStatusPill status={it.status} />
          </div>
          <div style={{ fontSize: 11.5, color: T.ink3, marginTop: 3 }}>
            编码 <span style={{ color: T.ink2, fontFamily: 'ui-monospace, monospace' }}>{it.code}</span>
            <span style={{ margin: '0 6px', color: T.outline }}>·</span>
            分类 <span style={{ color: T.ink2 }}>{it.cat}</span>
          </div>
        </div>
      </div>

      {/* 发放/归还 时间轴 */}
      <div style={{ padding: '12px', display: 'flex', gap: 8 }}>
        {[
          { label: '发放', date: it.issueDate, time: it.issueTime, who: it.issuer, done: true },
          { label: '归还', date: it.returnDate, time: it.returnTime, who: it.receiver, done: it.returnDate !== '——' },
        ].map((x, i) => (
          <div key={i} style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 4 }}>
              <span style={{ width: 7, height: 7, borderRadius: 999, background: x.done ? (i === 0 ? T.primary : T.success) : T.outline }} />
              <span style={{ fontSize: 11, fontWeight: 600, color: x.done ? T.ink2 : T.ink3 }}>{x.label}</span>
            </div>
            <div style={{ fontSize: 12.5, color: x.done ? T.ink : T.ink3, fontFamily: 'ui-monospace, monospace' }}>{x.date}</div>
            <div style={{ fontSize: 11, color: T.ink3, fontFamily: 'ui-monospace, monospace' }}>{x.time}</div>
            <div style={{ fontSize: 11, color: T.ink3, marginTop: 3 }}>{x.who}</div>
          </div>
        ))}
      </div>

      {/* 赔偿 + 备注 */}
      <div style={{ padding: '0 12px 10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '8px 0', borderTop: `1px solid ${T.outline}25` }}>
          <span style={{ fontSize: 12.5, color: T.ink3 }}>赔偿金额</span>
          <span style={{ fontSize: 13, fontWeight: 700, color: it.comp > 0 ? T.danger : T.ink2 }}>{money(it.comp)}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '8px 0', borderTop: `1px solid ${T.outline}25` }}>
          <span style={{ fontSize: 12.5, color: T.ink3 }}>备注</span>
          <button style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: 'transparent',
            border: 'none', cursor: 'pointer', color: it.note ? T.ink : T.ink3, fontSize: 12.5, fontFamily: 'Lexend' }}>
            {it.note || '添加备注'}
            <MaterialIcon name="edit" size={13} color={T.primary} />
          </button>
        </div>
      </div>

      {/* 操作条 */}
      <div style={{ padding: '0 12px 10px' }}>
        <div style={{ display: 'flex', gap: 7 }}>
          {issued && <ActionBtn icon="assignment_returned" label="归还" variant="primary" />}
          {issued && <ActionBtn icon="inventory" label="暂存" variant="ghost" />}
          <ActionBtn icon="swap_horiz" label="更换" variant="ghost" onClick={() => onSwap && onSwap(it)} />
          <ActionBtn icon="gavel" label="赔偿" variant="danger" />
        </div>
      </div>

      {/* 发放记录 */}
      <div style={{ padding: '0 12px 4px' }}>
        <DispatchLog rows={it.dispatchLog} />
      </div>
    </div>
  );
}

// 租赁物明细（嵌套折叠，含多件租赁物卡）
function ItemDetail({ items, onSwap }) {
  const [open, setOpen] = React.useState(true);
  return (
    <div style={{ borderTop: `1px solid ${T.outline}30` }}>
      <button onClick={() => setOpen(!open)} style={{ width: '100%', cursor: 'pointer', background: 'transparent',
        border: 'none', padding: '10px 0', display: 'flex', alignItems: 'center', gap: 6, fontFamily: 'Lexend' }}>
        <MaterialIcon name="snowboarding" size={15} color={T.primary} />
        <span style={{ fontSize: 13, fontWeight: 600, color: T.ink }}>租赁物明细</span>
        <span style={{ fontSize: 11, color: T.ink3 }}>{items.length} 件</span>
        <MaterialIcon name={open ? 'expand_less' : 'expand_more'} size={18} color={T.ink3} style={{ marginLeft: 'auto' }} />
      </button>
      {open && (
        <div style={{ paddingBottom: 6, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {items.map((it, i) => <RentalItemCard key={i} it={it} onSwap={onSwap} />)}
        </div>
      )}
    </div>
  );
}

// ── 单个租赁商品卡（折叠态 → 展开明细） ──────────────
function ProductCard({ p, idx, onSwap }) {
  const [open, setOpen] = React.useState(idx === 0);
  return (
    <div style={{ border: `1px solid ${T.outline}40`, borderRadius: 10, overflow: 'hidden', background: T.surface }}>
      {/* 折叠态头 */}
      <button onClick={() => setOpen(!open)} style={{ width: '100%', textAlign: 'left', cursor: 'pointer',
        background: open ? T.surfaceLow : T.surface, border: 'none', padding: '12px',
        display: 'flex', gap: 10, alignItems: 'flex-start', fontFamily: 'Lexend' }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: T.ink3, flexShrink: 0, paddingTop: 1 }}>{idx + 1}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            <span style={{ padding: '2px 6px', borderRadius: 4, background: p.kind === '套餐' ? T.primary : T.surface3,
              color: p.kind === '套餐' ? '#fff' : T.primary, fontSize: 10, fontWeight: 700, lineHeight: 1 }}>{p.kind}</span>
            <span style={{ fontSize: 14, fontWeight: 700, color: T.ink, lineHeight: 1.35 }}>{p.name}</span>
            <span style={{ fontSize: 11, color: T.ink3 }}>· {p.unit}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginTop: 8 }}>
            <span style={{ fontSize: 12, color: T.ink3 }}>押金 <b style={{ color: T.ink, fontWeight: 700 }}>{money(p.deposit)}</b></span>
            <span style={{ fontSize: 12, color: T.ink3 }}>租金 <b style={{ color: T.primary, fontWeight: 700 }}>{money(p.subtotal)}</b></span>
          </div>
        </div>
        <MaterialIcon name={open ? 'expand_less' : 'expand_more'} size={20} color={T.ink3} />
      </button>

      {/* 展开明细 */}
      {open && (
        <div style={{ padding: '12px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <RentPeriod p={p} />
          <FeeBreakdown p={p} />

          {/* 备注（商品级） */}
          <div style={{ display: 'flex', gap: 8 }}>
            <input defaultValue={p.note} placeholder="输入商品备注" style={{ flex: 1, height: 38, borderRadius: 9,
              border: `1px solid ${T.outline}50`, padding: '0 12px', fontSize: 13, color: T.ink,
              fontFamily: 'Lexend', outline: 'none', background: T.surface }} />
            <button style={{ height: 38, padding: '0 14px', borderRadius: 9, border: `1px solid ${T.outline}60`,
              background: T.surface, color: T.ink, fontSize: 13, fontWeight: 600, cursor: 'pointer',
              fontFamily: 'Lexend', flexShrink: 0 }}>保存</button>
          </div>

          {/* 嵌套：租金明细 + 租赁物明细 */}
          <div style={{ borderTop: `1px solid ${T.outline}30`, paddingTop: 2 }}>
            <RentDetail rows={p.rentDetail} />
            <ItemDetail items={p.items} onSwap={onSwap} />
          </div>
        </div>
      )}
    </div>
  );
}

// ── 租赁信息 + Tab ──────────────────────────────
function RentalInfo({ d, onSwap }) {
  const [tab, setTab] = React.useState('product');
  const allItems = d.products.flatMap(p => p.items.map(it => ({ ...it, product: p.name, kind: p.kind })));
  return (
    <section style={{ margin: '12px 12px 0', borderRadius: 12, background: T.surface,
      border: `1px solid ${T.outline}30`, padding: '14px 16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <MaterialIcon name="inventory_2" size={16} color={T.primary} />
        <span style={{ fontSize: 14, fontWeight: 700, color: T.ink, fontFamily: 'Lexend' }}>租赁信息</span>
        <span style={{ fontSize: 12, color: T.ink3, marginLeft: 'auto' }}>共 {d.products.length} 项</span>
      </div>
      <div style={{ display: 'flex', background: T.surfaceLow, borderRadius: 10, padding: 4, marginBottom: 12 }}>
        {[{ k: 'product', label: '按租赁商品' }, { k: 'item', label: '按租赁物' }].map(t => {
          const active = tab === t.k;
          return (
            <button key={t.k} onClick={() => setTab(t.k)} style={{ flex: 1, height: 32, borderRadius: 7, border: 'none',
              cursor: 'pointer', background: active ? T.surface : 'transparent', color: active ? T.primary : T.ink2,
              fontSize: 13, fontWeight: active ? 700 : 500, fontFamily: 'Lexend',
              boxShadow: active ? '0 1px 2px rgba(0,0,0,0.04)' : 'none' }}>{t.label}</button>
          );
        })}
      </div>
      {tab === 'product' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {d.products.map((p, i) => <ProductCard key={i} p={p} idx={i} onSwap={onSwap} />)}
        </div>
      )}
      {tab === 'item' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {allItems.map((it, i) => <RentalItemCard key={i} it={it} onSwap={onSwap} />)}
        </div>
      )}
    </section>
  );
}

// ── 退款汇总 ──────────────────────────────
function RefundCard({ s }) {
  const [actual, setActual] = React.useState(s.actual);
  return (
    <Collapsible title="退款" icon="account_balance_wallet" defaultOpen={false}
      summary={`应退 ${money(s.refundableDeposit)}`}>
      <div style={{ background: T.surfaceLow, borderRadius: 10, padding: 12, margin: '4px 0 0' }}>
        <FieldGrid rows={[
          ['总计押金', money(s.totalDeposit), '总计租金', money(s.totalRent)],
          ['总计超时', money(s.totalOvertime), '总计赔偿', money(s.totalComp)],
        ]} />
        <div style={{ borderTop: `1px solid ${T.outline}40`, marginTop: 8, paddingTop: 8 }}>
          <FieldGrid rows={[
            ['应退押金', money(s.refundableDeposit), '已退金额', money(s.refunded)],
          ]} />
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 12 }}>
        <span style={{ fontSize: 13, color: T.ink3, flexShrink: 0 }}>实际应退</span>
        <input value={actual} onChange={(e) => setActual(e.target.value)} style={{ flex: 1, height: 40, borderRadius: 8,
          border: `1px solid ${T.outline}50`, padding: '0 12px', fontSize: 14, color: T.ink, fontWeight: 600,
          fontFamily: 'Lexend', outline: 'none', background: T.surface }} />
        <button style={{ height: 40, padding: '0 22px', borderRadius: 8, border: 'none', background: T.danger,
          color: '#fff', fontSize: 14, fontWeight: 700, cursor: 'pointer', fontFamily: 'Lexend', flexShrink: 0 }}>退款</button>
      </div>
    </Collapsible>
  );
}

// ── 底部操作栏 ──────────────────────────────
function BottomBar() {
  return (
    <footer style={{ position: 'sticky', bottom: 0, zIndex: 30, background: T.surface,
      borderTop: `1px solid ${T.outline}40`, padding: '10px 12px', display: 'flex', gap: 8, alignItems: 'center' }}>
      <button style={ghostBtn}><MaterialIcon name="add_box" size={16} color={T.ink} />添加套餐</button>
      <button style={ghostBtn}><MaterialIcon name="add" size={16} color={T.ink} />添加单品</button>
      <button style={{ flex: 1.4, height: 44, borderRadius: 10, border: 'none', background: T.primary, color: '#fff',
        fontSize: 14, fontWeight: 700, cursor: 'pointer', fontFamily: 'Lexend',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
        <MaterialIcon name="check" size={16} color="#fff" fill={1} />确认追加</button>
    </footer>
  );
}
const ghostBtn = { flex: 1, height: 44, borderRadius: 10, border: `1px solid ${T.outline}50`, background: T.surface,
  color: T.ink, fontSize: 13.5, fontWeight: 600, cursor: 'pointer', fontFamily: 'Lexend',
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 5 };

// ── 页面 ──────────────────────────────
// ── 更换租赁物页（全屏覆盖层） ──────────────
// 上：现租赁物（只读） 下：新租赁物表单（规则参考新增租赁物）
function SwapItemPage({ item, onClose }) {
  const [noCode, setNoCode] = React.useState(true);
  const [code, setCode] = React.useState('');
  const [cat, setCat] = React.useState(item ? item.cat : '头盔');
  const [name, setName] = React.useState('');
  const [note, setNote] = React.useState('');
  const cats = ['头盔', '【双板】竞技双板', '【单板鞋】Burton', '【护具】套装', '雪镜'];

  const RORow = ({ label, value, mono }) => (
    <div style={{ display: 'flex', alignItems: 'center', minHeight: 44, padding: '0 14px',
      borderTop: `1px solid ${T.outline}25`, gap: 12 }}>
      <span style={{ fontSize: 13, color: T.ink3, width: 76, flexShrink: 0 }}>{label}</span>
      <span style={{ flex: 1, fontSize: 13.5, fontWeight: 600, color: T.ink2,
        fontFamily: mono ? 'ui-monospace, monospace' : 'Lexend' }}>{value}</span>
    </div>
  );

  const FieldRow = ({ label, children, required }) => (
    <div style={{ display: 'flex', alignItems: 'flex-start', padding: '12px 14px', gap: 12,
      borderTop: `1px solid ${T.outline}25` }}>
      <span style={{ fontSize: 13.5, color: T.ink2, fontWeight: 500, width: 56, flexShrink: 0, paddingTop: 9 }}>
        {required && <span style={{ color: T.danger, marginRight: 2 }}>*</span>}{label}
      </span>
      <div style={{ flex: 1 }}>{children}</div>
    </div>
  );

  const inputStyle = { width: '100%', height: 40, borderRadius: 9, border: `1px solid ${T.outline}55`,
    padding: '0 12px', fontSize: 14, color: T.ink, fontFamily: 'Lexend', outline: 'none', background: T.surface };

  return (
    <div style={{ position: 'absolute', inset: 0, zIndex: 120, background: T.bg,
      display: 'flex', flexDirection: 'column', fontFamily: 'Lexend, system-ui' }}>
      <header style={{ height: 52, background: T.surface, borderBottom: `1px solid ${T.outline}40`,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 12px', flexShrink: 0 }}>
        <button onClick={onClose} style={btn}><MaterialIcon name="arrow_back_ios_new" size={20} color={T.primary} /></button>
        <h1 style={{ fontFamily: 'Lexend', fontWeight: 700, fontSize: 17, color: T.primary, margin: 0 }}>更换租赁物</h1>
        <div style={{ width: 36 }} />
      </header>

      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 12px 0' }}>
        {/* 现租赁物（只读） */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '2px 4px 8px' }}>
            <span style={{ width: 3, height: 14, borderRadius: 2, background: T.ink3 }} />
            <span style={{ fontSize: 13, fontWeight: 700, color: T.ink2 }}>现租赁物</span>
            <span style={{ fontSize: 11, color: T.ink3 }}>待替换</span>
          </div>
          <div style={{ background: T.surfaceLow, borderRadius: 11, border: `1px solid ${T.outline}30`,
            overflow: 'hidden', opacity: 0.95 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '11px 14px' }}>
              <div style={{ width: 34, height: 34, borderRadius: 8, background: T.surface,
                border: `1px solid ${T.outline}40`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <MaterialIcon name="sports_motorsports" size={19} color={T.ink3} />
              </div>
              <div>
                <div style={{ fontSize: 15, fontWeight: 700, color: T.ink2 }}>{item ? item.name : '—'}</div>
                <div style={{ fontSize: 11, color: T.ink3 }}>{item ? item.cat : '—'}</div>
              </div>
            </div>
            <RORow label="编码" value={item ? item.code : '—'} mono />
            <RORow label="名称" value={item ? item.name : '—'} />
            <RORow label="分类" value={item ? item.cat : '—'} />
            <RORow label="发放人" value={item ? item.issuer : '—'} />
            <RORow label="发放时间" value={item ? `${item.issueDate} ${item.issueTime}` : '—'} mono />
          </div>
        </div>

        {/* 新租赁物（表单） */}
        <div style={{ paddingBottom: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '2px 4px 8px' }}>
            <span style={{ width: 3, height: 14, borderRadius: 2, background: T.primary }} />
            <span style={{ fontSize: 13, fontWeight: 700, color: T.primary }}>新租赁物</span>
            <span style={{ fontSize: 11, color: T.ink3 }}>规则同新增租赁物</span>
          </div>
          <div style={{ background: T.surface, borderRadius: 11, border: `1px solid ${T.outline}30`, overflow: 'hidden' }}>
            <FieldRow label="编码">
              <div style={{ display: 'flex', gap: 8 }}>
                <input value={code} onChange={(e) => setCode(e.target.value)} disabled={noCode}
                  placeholder={noCode ? '无编码' : '输入或扫码录入'}
                  style={{ ...inputStyle, flex: 1, background: noCode ? T.surfaceLow : T.surface,
                    color: noCode ? T.ink3 : T.ink }} />
                <button disabled={noCode} style={{ width: 40, height: 40, borderRadius: 9, flexShrink: 0,
                  border: `1px solid ${noCode ? T.outline + '40' : T.primary}`, cursor: noCode ? 'not-allowed' : 'pointer',
                  background: noCode ? T.surfaceLow : '#e0f2ff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <MaterialIcon name="qr_code_scanner" size={20} color={noCode ? T.ink3 : T.primary} />
                </button>
              </div>
            </FieldRow>

            <FieldRow label="无编码">
              <div style={{ display: 'flex', alignItems: 'center', height: 40 }}>
                <button onClick={() => setNoCode(!noCode)} style={{ width: 46, height: 28, borderRadius: 999,
                  border: 'none', cursor: 'pointer', padding: 2, background: noCode ? T.primary : T.outline + '60',
                  display: 'flex', justifyContent: noCode ? 'flex-end' : 'flex-start', transition: 'all .15s' }}>
                  <span style={{ width: 24, height: 24, borderRadius: 999, background: '#fff',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.2)' }} />
                </button>
                <span style={{ marginLeft: 10, fontSize: 12.5, color: T.ink3 }}>
                  {noCode ? '该租赁物无物理编码' : '请输入/扫描编码'}
                </span>
              </div>
            </FieldRow>

            <FieldRow label="分类" required>
              <div style={{ position: 'relative' }}>
                <select value={cat} onChange={(e) => setCat(e.target.value)}
                  style={{ ...inputStyle, appearance: 'none', WebkitAppearance: 'none', cursor: 'pointer', paddingRight: 34 }}>
                  {cats.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
                <span style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}>
                  <MaterialIcon name="expand_more" size={18} color={T.ink3} />
                </span>
              </div>
            </FieldRow>

            <FieldRow label="名称" required>
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="输入租赁物名称" style={inputStyle} />
            </FieldRow>

            <FieldRow label="备注">
              <textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="选填" rows={3}
                style={{ ...inputStyle, height: 'auto', padding: '10px 12px', resize: 'none', lineHeight: 1.5 }} />
            </FieldRow>
          </div>

          <p style={{ fontSize: 11.5, color: T.ink3, margin: '10px 4px 0', lineHeight: 1.5 }}>
            确认后：原租赁物自动归还，新租赁物按当前租赁商品发放，押金与租金保持不变。
          </p>
        </div>
      </div>

      <footer style={{ flexShrink: 0, background: T.surface, borderTop: `1px solid ${T.outline}40`,
        padding: '10px 12px', display: 'flex', gap: 10 }}>
        <button onClick={onClose} style={{ flex: 1, height: 46, borderRadius: 11, cursor: 'pointer',
          border: `1px solid ${T.outline}55`, background: T.surface, color: T.ink2,
          fontSize: 15, fontWeight: 600, fontFamily: 'Lexend' }}>取消</button>
        <button onClick={onClose} style={{ flex: 2, height: 46, borderRadius: 11, cursor: 'pointer',
          border: 'none', background: T.primary, color: '#fff', fontSize: 15, fontWeight: 700, fontFamily: 'Lexend',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
          <MaterialIcon name="check" size={18} color="#fff" fill={1} />确认更换
        </button>
      </footer>
    </div>
  );
}

// ── 页面 ──
function DetailPage({ onBack, data }) {
  const d = data || DETAIL;
  const [swapItem, setSwapItem] = React.useState(null);
  return (
    <div style={{ width: '100%', height: '100%', background: T.bg, color: T.ink,
      fontFamily: 'Lexend, system-ui', display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative' }}>
      <AppBar onBack={onBack} />
      <div style={{ flex: 1, overflowY: 'auto', paddingBottom: 14 }}>
        <OrderInfo d={d} />
        <PaymentInfo d={d} />
        <RentalInfo d={d} onSwap={setSwapItem} />
        <RefundCard s={d.refundSummary} />
        <div style={{ height: 4 }} />
      </div>
      <BottomBar />
      {swapItem && <SwapItemPage item={swapItem} onClose={() => setSwapItem(null)} />}
    </div>
  );
}

window.DetailPage = DetailPage;
window.SnowmeetDetailMock = DETAIL;

// 独立演示：直接展示"更换租赁物"页（用首件租赁物作为现租赁物）
function SwapItemDemo() {
  const item = DETAIL.products[0].items[0];
  return (
    <div style={{ width: '100%', height: '100%', position: 'relative', background: T.bg, overflow: 'hidden' }}>
      <SwapItemPage item={item} onClose={() => {}} />
    </div>
  );
}
window.SwapItemDemo = SwapItemDemo;
window.SwapItemPage = SwapItemPage;

})();
