// 店长远程注册会员 — 手机号检测 → 新建/已存在分支 → 填写资料+初始储值/券 → 注册并短信通知
(() => {
const { useMember, MIcon, mmoney, MEMBERS, Avatar, GenderChip, AppBar } = window;

function Banner() {
  const { T } = useMember();
  return (
    <div style={{ margin: '12px 12px 0', borderRadius: 12, background: T.primaryFixed, border: `1px solid ${T.primaryFixedDim}`,
      padding: '11px 13px', display: 'flex', gap: 9 }}>
      <MIcon name="cell_tower" size={18} color={T.primary} fill={1} style={{ marginTop: 1 }} />
      <div style={{ fontSize: 12, color: T.primary, lineHeight: 1.5 }}>
        <b>远程注册</b>：顾客不在店时，仅凭手机号即可创建会员并直接办理二手回收结算、预约租赁 / 养护等业务，系统将短信通知顾客。
      </div>
    </div>
  );
}

function Card({ title, children }) {
  const { T } = useMember();
  return (
    <section style={{ margin: '12px 12px 0', borderRadius: 12, background: T.surface, border: `1px solid ${T.outline}30`, padding: '14px 16px' }}>
      {title && <div style={{ fontSize: 13, fontWeight: 700, color: T.ink, marginBottom: 11 }}>{title}</div>}
      {children}
    </section>
  );
}

function GenderSeg({ value, onChange }) {
  const { T } = useMember();
  return (
    <div style={{ display: 'flex', background: T.surfaceLow, borderRadius: 9, padding: 3, gap: 3, width: 160 }}>
      {['男', '女'].map((g) => {
        const on = value === g;
        return (
          <button key={g} onClick={() => onChange(g)} style={{ flex: 1, height: 32, borderRadius: 7, border: 'none', cursor: 'pointer',
            background: on ? T.surface : 'transparent', color: on ? T.primary : T.ink2, fontSize: 13, fontWeight: on ? 700 : 500,
            fontFamily: 'Lexend', boxShadow: on ? '0 1px 2px rgba(0,0,0,0.06)' : 'none' }}>{g}</button>
        );
      })}
    </div>
  );
}

function AmountInput({ k, label, value, onChange, accentFg, accentBg }) {
  const { T } = useMember();
  return (
    <div style={{ flex: 1 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 6 }}>
        <span style={{ display: 'inline-flex', width: 16, height: 16, borderRadius: 4, background: accentBg, color: accentFg,
          fontSize: 10, fontWeight: 800, alignItems: 'center', justifyContent: 'center' }}>{k}</span>
        <span style={{ fontSize: 11.5, color: T.ink3 }}>{label}</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', height: 38, borderRadius: 9, border: `1px solid ${T.outline}55`, background: T.surface, padding: '0 10px' }}>
        <span style={{ fontSize: 13, color: T.ink3 }}>¥</span>
        <input value={value} onChange={(e) => onChange(e.target.value.replace(/[^0-9.]/g, ''))} placeholder="0"
          inputMode="decimal" style={{ flex: 1, minWidth: 0, border: 'none', outline: 'none', background: 'transparent',
            fontSize: 14, fontWeight: 600, color: T.ink, fontFamily: 'ui-monospace, monospace', textAlign: 'right' }} />
      </div>
    </div>
  );
}

function MemberRegisterPage({ onBack, onViewMember }) {
  const { T } = useMember();
  const [phone, setPhone] = React.useState('');
  const [phase, setPhase] = React.useState('idle'); // idle | existing | new | done
  const [found, setFound] = React.useState(null);
  const [form, setForm] = React.useState({ name: '', gender: '男', a: '', b: '', c: '', coupon: true, biz: [] });
  const [newId, setNewId] = React.useState('');

  const valid = /^1\d{10}$/.test(phone);
  const detect = () => {
    const hit = MEMBERS.find((m) => m.phone === phone);
    if (hit) { setFound(hit); setPhase('existing'); }
    else { setPhase('new'); }
  };
  const reset = () => { setPhone(''); setPhase('idle'); setFound(null); setForm({ name: '', gender: '男', a: '', b: '', c: '', coupon: true, biz: [] }); };
  const submit = () => { setNewId(String(220000 + Math.floor(Math.random() * 19999))); setPhase('done'); };
  const toggleBiz = (b) => setForm((f) => ({ ...f, biz: f.biz.includes(b) ? f.biz.filter((x) => x !== b) : [...f.biz, b] }));

  const fieldStyle = { width: '100%', height: 40, borderRadius: 9, border: `1px solid ${T.outline}55`, padding: '0 12px',
    fontSize: 14, color: T.ink, fontFamily: 'Lexend', outline: 'none', background: T.surface, boxSizing: 'border-box' };
  const labelStyle = { fontSize: 12.5, fontWeight: 600, color: T.ink2, marginBottom: 7, display: 'block' };

  return (
    <div style={{ width: '100%', height: '100%', background: T.bg, color: T.ink, fontFamily: 'Lexend, system-ui',
      display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <AppBar title="注册会员" onBack={onBack} />
      <div style={{ flex: 1, overflowY: 'auto', paddingBottom: 16 }}>
        <Banner />

        {/* 手机号检测 */}
        <Card title="会员手机号">
          <div style={{ display: 'flex', gap: 8 }}>
            <input value={phone} onChange={(e) => { setPhone(e.target.value.replace(/[^0-9]/g, '').slice(0, 11)); setPhase('idle'); }}
              placeholder="输入顾客 11 位手机号" inputMode="numeric"
              style={{ ...fieldStyle, fontFamily: 'ui-monospace, monospace', letterSpacing: 0.5 }} />
            <button onClick={detect} disabled={!valid} style={{ height: 40, padding: '0 18px', borderRadius: 9, border: 'none', flexShrink: 0,
              background: valid ? T.primary : T.surface2, color: valid ? '#fff' : T.ink3, fontSize: 14, fontWeight: 700,
              cursor: valid ? 'pointer' : 'not-allowed', fontFamily: 'Lexend' }}>检测</button>
          </div>
          {phase === 'idle' && <p style={{ fontSize: 11.5, color: T.ink3, margin: '9px 2px 0' }}>一个手机号只能认证一个会员 ID</p>}
        </Card>

        {/* 已存在 */}
        {phase === 'existing' && found && (
          <Card>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 12, color: T.warn }}>
              <MIcon name="info" size={17} color={T.warn} fill={1} />
              <span style={{ fontSize: 13, fontWeight: 600 }}>该手机号已是会员，可直接办理业务</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '4px 0 14px' }}>
              <Avatar name={found.name} gender={found.gender} size={46} />
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                  <span style={{ fontSize: 16, fontWeight: 700 }}>{found.name}</span><GenderChip gender={found.gender} />
                </div>
                <div style={{ fontSize: 12, color: T.ink3, marginTop: 3 }}>会员 ID <span style={{ fontFamily: 'ui-monospace, monospace', color: T.ink2 }}>{found.id}</span> · 储值合计 {mmoney(found.sv.a + found.sv.b + found.sv.c)}</div>
              </div>
            </div>
            <button onClick={() => onViewMember && onViewMember(found)} style={{ width: '100%', height: 46, borderRadius: 11, border: 'none',
              background: T.primary, color: '#fff', fontSize: 15, fontWeight: 700, cursor: 'pointer', fontFamily: 'Lexend',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
              <MIcon name="arrow_forward" size={18} color="#fff" />进入会员详情办理业务
            </button>
          </Card>
        )}

        {/* 新建表单 */}
        {phase === 'new' && (
          <>
            <Card>
              <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 13, color: T.success }}>
                <MIcon name="check_circle" size={17} color={T.success} fill={1} />
                <span style={{ fontSize: 13, fontWeight: 600 }}>手机号未注册，将创建新会员</span>
              </div>
              <div style={{ marginBottom: 14 }}>
                <label style={labelStyle}>姓名 / 称呼<span style={{ color: T.ink3, fontWeight: 400 }}>（选填）</span></label>
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="如：王女士" style={fieldStyle} />
              </div>
              <div>
                <label style={labelStyle}>性别</label>
                <GenderSeg value={form.gender} onChange={(g) => setForm({ ...form, gender: g })} />
              </div>
            </Card>

            <Card title="初始储值（选填）">
              <div style={{ display: 'flex', gap: 8 }}>
                <AmountInput k="A" label="全平台" value={form.a} onChange={(v) => setForm({ ...form, a: v })} accentFg={T.primary} accentBg={T.primaryFixed} />
                <AmountInput k="B" label="服务+指定" value={form.b} onChange={(v) => setForm({ ...form, b: v })} accentFg={T.success} accentBg={T.successBg} />
                <AmountInput k="C" label="二手回收" value={form.c} onChange={(v) => setForm({ ...form, c: v })} accentFg={T.violet} accentBg={T.violetBg} />
              </div>
              <p style={{ fontSize: 11, color: T.ink3, margin: '9px 2px 0' }}>二手装备回收结算通常发放 C 类储值（仅租赁 / 养护可用）</p>
            </Card>

            <Card title="附加办理（选填）">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '2px 0 12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <MIcon name="redeem" size={18} color={T.primary} />
                  <span style={{ fontSize: 13.5, color: T.ink }}>发放新人优惠券</span>
                </div>
                <button onClick={() => setForm({ ...form, coupon: !form.coupon })} style={{ width: 46, height: 28, borderRadius: 999, border: 'none',
                  cursor: 'pointer', padding: 2, background: form.coupon ? T.primary : T.outline + '80',
                  display: 'flex', justifyContent: form.coupon ? 'flex-end' : 'flex-start', transition: 'all .15s' }}>
                  <span style={{ width: 24, height: 24, borderRadius: 999, background: '#fff', boxShadow: '0 1px 3px rgba(0,0,0,0.2)' }} />
                </button>
              </div>
              <div style={{ borderTop: `1px solid ${T.outline}22`, paddingTop: 12 }}>
                <span style={{ fontSize: 12.5, color: T.ink3, display: 'block', marginBottom: 8 }}>预约业务</span>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
                  {['租赁预约', '养护预约', '雪票'].map((b) => {
                    const on = form.biz.includes(b);
                    return (
                      <button key={b} onClick={() => toggleBiz(b)} style={{ height: 32, padding: '0 13px', borderRadius: 999, cursor: 'pointer',
                        border: `1px solid ${on ? T.primary : T.outline + '55'}`, background: on ? T.primaryFixed : T.surface,
                        color: on ? T.primary : T.ink2, fontSize: 12.5, fontWeight: on ? 700 : 500, fontFamily: 'Lexend' }}>{b}</button>
                    );
                  })}
                </div>
              </div>
            </Card>
          </>
        )}

        {/* 完成 */}
        {phase === 'done' && (
          <Card>
            <div style={{ textAlign: 'center', padding: '10px 0 6px' }}>
              <div style={{ width: 58, height: 58, borderRadius: 999, background: T.successBg, margin: '0 auto',
                display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <MIcon name="check" size={32} color={T.success} fill={1} weight={600} />
              </div>
              <h2 style={{ fontSize: 18, fontWeight: 700, color: T.ink, margin: '12px 0 4px' }}>注册成功</h2>
              <p style={{ fontSize: 12.5, color: T.ink3, margin: 0 }}>已为顾客创建会员账户</p>
            </div>
            <div style={{ background: T.surfaceLow, borderRadius: 11, padding: 14, margin: '14px 0' }}>
              {[['会员 ID', newId, true], ['认证手机号', phone, true], ['姓名', form.name || '未填写', false],
                ['初始储值', `A ${mmoney(+form.a || 0)} · B ${mmoney(+form.b || 0)} · C ${mmoney(+form.c || 0)}`, false],
                ['新人券', form.coupon ? '已发放' : '未发放', false]].map(([l, v, mono]) => (
                <div key={l} style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0', fontSize: 13 }}>
                  <span style={{ color: T.ink3 }}>{l}</span>
                  <span style={{ fontWeight: 600, color: T.ink, fontFamily: mono ? 'ui-monospace, monospace' : 'Lexend' }}>{v}</span>
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '10px 12px', borderRadius: 10,
              background: T.primaryFixed, color: T.primary, fontSize: 12.5, marginBottom: 14 }}>
              <MIcon name="sms" size={16} color={T.primary} fill={1} />
              <span>已发送短信通知：含会员 ID 与微信扫码登录二维码</span>
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button onClick={reset} style={{ flex: 1, height: 46, borderRadius: 11, border: `1px solid ${T.outline}55`,
                background: T.surface, color: T.ink2, fontSize: 14, fontWeight: 600, cursor: 'pointer', fontFamily: 'Lexend' }}>再注册一个</button>
              <button onClick={() => onViewMember && onViewMember(MEMBERS[0])} style={{ flex: 1.4, height: 46, borderRadius: 11, border: 'none',
                background: T.primary, color: '#fff', fontSize: 14, fontWeight: 700, cursor: 'pointer', fontFamily: 'Lexend',
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
                <MIcon name="badge" size={17} color="#fff" />查看会员详情
              </button>
            </div>
          </Card>
        )}
      </div>

      {/* 底部操作（新建表单时） */}
      {phase === 'new' && (
        <footer style={{ flexShrink: 0, background: T.surface, borderTop: `1px solid ${T.outline}40`, padding: '10px 12px', display: 'flex', gap: 10 }}>
          <button onClick={reset} style={{ flex: 1, height: 46, borderRadius: 11, border: `1px solid ${T.outline}55`,
            background: T.surface, color: T.ink2, fontSize: 15, fontWeight: 600, cursor: 'pointer', fontFamily: 'Lexend' }}>重置</button>
          <button onClick={submit} style={{ flex: 2, height: 46, borderRadius: 11, border: 'none', background: T.primary, color: '#fff',
            fontSize: 15, fontWeight: 700, cursor: 'pointer', fontFamily: 'Lexend', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
            <MIcon name="person_add" size={18} color="#fff" fill={1} />注册并发送短信
          </button>
        </footer>
      )}
    </div>
  );
}

// 独立演示（注册 artboard）—— 预置一个未注册手机号，停在新建表单
function MemberRegisterDemo() {
  return <MemberRegisterPage />;
}

window.MemberRegisterPage = MemberRegisterPage;
window.MemberRegisterDemo = MemberRegisterDemo;

})();
