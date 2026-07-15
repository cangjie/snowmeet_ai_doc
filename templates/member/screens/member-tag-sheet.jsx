// 自定义标签编辑弹层 — 系统标签只读 + 当前标签可删 + 手输新增 + 预设库勾选
(() => {
const { useMember, MIcon, SYS_TAGS, PRESET_TAGS, MEMBERS, SystemTagChip } = window;

function MemberTagSheet({ sys = [], value = [], onClose, onSave }) {
  const { T } = useMember();
  const [sel, setSel] = React.useState(value);
  const [text, setText] = React.useState('');

  const has = (t) => sel.includes(t);
  const toggle = (t) => setSel(has(t) ? sel.filter((x) => x !== t) : [...sel, t]);
  const remove = (t) => setSel(sel.filter((x) => x !== t));
  const add = () => {
    const v = text.trim();
    if (v && !sel.includes(v)) setSel([...sel, v]);
    setText('');
  };
  const presetSet = new Set(PRESET_TAGS.flatMap((g) => g.items));
  const customExtra = sel.filter((t) => !presetSet.has(t)); // 手输的、库里没有的

  return (
    <div style={{ position: 'absolute', inset: 0, zIndex: 120, display: 'flex', flexDirection: 'column',
      justifyContent: 'flex-end', fontFamily: 'Lexend, system-ui' }}>
      <div onClick={onClose} style={{ position: 'absolute', inset: 0, background: 'rgba(11,28,48,0.45)', animation: 'mbFade .2s ease' }} />
      <div style={{ position: 'relative', background: T.bg, borderTopLeftRadius: 20, borderTopRightRadius: 20,
        maxHeight: '93%', display: 'flex', flexDirection: 'column', animation: 'mbSheetUp .26s cubic-bezier(.2,.8,.3,1)',
        boxShadow: '0 -8px 40px rgba(0,0,0,0.2)' }}>
        {/* 抓手 */}
        <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 8 }}>
          <span style={{ width: 38, height: 4, borderRadius: 999, background: T.outline }} />
        </div>
        {/* 头 */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 16px 12px' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: T.ink }}>编辑自定义标签</h2>
            <p style={{ margin: '2px 0 0', fontSize: 12, color: T.ink3 }}>系统标签不可编辑，仅维护自定义标签</p>
          </div>
          <button onClick={onClose} style={{ width: 30, height: 30, borderRadius: 999, border: 'none', background: T.surface2,
            display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
            <MIcon name="close" size={18} color={T.ink2} />
          </button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '0 16px 12px' }}>
          {/* 系统标签（只读） */}
          <div style={{ background: T.surface, borderRadius: 12, border: `1px solid ${T.outline}30`, padding: 13, marginBottom: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 9 }}>
              <MIcon name="lock" size={13} color={T.ink3} />
              <span style={{ fontSize: 12.5, fontWeight: 600, color: T.ink2 }}>系统标签</span>
              <span style={{ fontSize: 11, color: T.ink3 }}>按参与业务自动生成</span>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7, opacity: 0.95 }}>
              {sys.length ? sys.map((s) => <SystemTagChip key={s} name={s} />) : <span style={{ fontSize: 12, color: T.ink3 }}>暂无</span>}
            </div>
          </div>

          {/* 当前自定义标签 */}
          <div style={{ background: T.surface, borderRadius: 12, border: `1px solid ${T.outline}30`, padding: 13, marginBottom: 12 }}>
            <div style={{ fontSize: 12.5, fontWeight: 600, color: T.ink2, marginBottom: 9 }}>
              当前自定义标签 <span style={{ color: T.primary }}>{sel.length}</span>
            </div>
            {sel.length ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
                {sel.map((t) => (
                  <span key={t} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '5px 7px 5px 11px',
                    borderRadius: 8, background: T.primaryFixed, color: T.primary, fontSize: 12.5, fontWeight: 600 }}>
                    {t}
                    <button onClick={() => remove(t)} style={{ display: 'inline-flex', border: 'none', background: 'transparent', padding: 0, cursor: 'pointer' }}>
                      <MIcon name="cancel" size={15} color={T.primary} fill={1} />
                    </button>
                  </span>
                ))}
              </div>
            ) : <span style={{ fontSize: 12.5, color: T.ink3 }}>暂无，点击下方标签或手动添加</span>}

            {/* 手输新增 */}
            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
              <input value={text} onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') add(); }} placeholder="输入新标签后回车或点添加"
                style={{ flex: 1, height: 40, borderRadius: 9, border: `1px solid ${T.outline}55`, padding: '0 12px',
                  fontSize: 13.5, color: T.ink, fontFamily: 'Lexend', outline: 'none', background: T.surface, minWidth: 0 }} />
              <button onClick={add} disabled={!text.trim()} style={{ height: 40, padding: '0 16px', borderRadius: 9, border: 'none',
                background: text.trim() ? T.primary : T.surface2, color: text.trim() ? '#fff' : T.ink3,
                fontSize: 13.5, fontWeight: 700, cursor: text.trim() ? 'pointer' : 'not-allowed', fontFamily: 'Lexend', flexShrink: 0,
                display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <MIcon name="add" size={16} color={text.trim() ? '#fff' : T.ink3} />添加
              </button>
            </div>
          </div>

          {/* 预设标签库 */}
          <div style={{ background: T.surface, borderRadius: 12, border: `1px solid ${T.outline}30`, padding: 13 }}>
            <div style={{ fontSize: 12.5, fontWeight: 600, color: T.ink2, marginBottom: 4 }}>从标签库选择</div>
            {PRESET_TAGS.map((g) => (
              <div key={g.group} style={{ marginTop: 11 }}>
                <div style={{ fontSize: 11, color: T.ink3, marginBottom: 7 }}>{g.group}</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
                  {g.items.map((t) => {
                    const on = has(t);
                    return (
                      <button key={t} onClick={() => toggle(t)} style={{ display: 'inline-flex', alignItems: 'center', gap: 4,
                        height: 32, padding: '0 12px', borderRadius: 999, cursor: 'pointer',
                        border: `1px solid ${on ? T.primary : T.outline + '55'}`, background: on ? T.primaryFixed : T.surface,
                        color: on ? T.primary : T.ink2, fontSize: 12.5, fontWeight: on ? 700 : 500, fontFamily: 'Lexend' }}>
                        <MIcon name={on ? 'check_circle' : 'add_circle'} size={14} color={on ? T.primary : T.ink3} fill={on ? 1 : 0} />{t}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
            {customExtra.length > 0 && (
              <div style={{ marginTop: 11 }}>
                <div style={{ fontSize: 11, color: T.ink3, marginBottom: 7 }}>手动添加</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
                  {customExtra.map((t) => (
                    <button key={t} onClick={() => toggle(t)} style={{ display: 'inline-flex', alignItems: 'center', gap: 4,
                      height: 32, padding: '0 12px', borderRadius: 999, cursor: 'pointer', border: `1px solid ${T.primary}`,
                      background: T.primaryFixed, color: T.primary, fontSize: 12.5, fontWeight: 700, fontFamily: 'Lexend' }}>
                      <MIcon name="check_circle" size={14} color={T.primary} fill={1} />{t}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* 底 */}
        <div style={{ flexShrink: 0, background: T.surface, borderTop: `1px solid ${T.outline}40`, padding: '10px 16px',
          display: 'flex', gap: 10, paddingBottom: 'max(10px, env(safe-area-inset-bottom))' }}>
          <button onClick={onClose} style={{ flex: 1, height: 46, borderRadius: 11, cursor: 'pointer',
            border: `1px solid ${T.outline}55`, background: T.surface, color: T.ink2, fontSize: 15, fontWeight: 600, fontFamily: 'Lexend' }}>取消</button>
          <button onClick={() => onSave(sel)} style={{ flex: 2, height: 46, borderRadius: 11, cursor: 'pointer', border: 'none',
            background: T.primary, color: '#fff', fontSize: 15, fontWeight: 700, fontFamily: 'Lexend',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
            <MIcon name="check" size={18} color="#fff" fill={1} />保存（{sel.length}）
          </button>
        </div>
      </div>
    </div>
  );
}

// 独立演示（标签编辑 artboard）
function MemberTagSheetDemo() {
  const { T } = useMember();
  const m = MEMBERS[0];
  const [val, setVal] = React.useState(m.custom);
  const [open, setOpen] = React.useState(true);
  return (
    <div style={{ width: '100%', height: '100%', background: T.bg, overflow: 'hidden', position: 'relative',
      display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ textAlign: 'center', color: T.ink3, padding: 20 }}>
        <MIcon name="sell" size={34} color={T.outline} />
        <div style={{ fontSize: 13, marginTop: 8 }}>{m.name} 的自定义标签</div>
        {!open && (
          <button onClick={() => setOpen(true)} style={{ marginTop: 12, height: 40, padding: '0 18px', borderRadius: 10,
            border: 'none', background: T.primary, color: '#fff', fontSize: 14, fontWeight: 700, cursor: 'pointer', fontFamily: 'Lexend' }}>打开编辑弹层</button>
        )}
      </div>
      {open && <MemberTagSheet sys={m.sys} value={val} onClose={() => setOpen(false)} onSave={(v) => { setVal(v); setOpen(false); }} />}
    </div>
  );
}

window.MemberTagSheet = MemberTagSheet;
window.MemberTagSheetDemo = MemberTagSheetDemo;

})();
