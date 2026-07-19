import { useEffect, useMemo, useState } from 'react';

const blankInbound = { type: 'mixed', tag: 'mixed-in', listen: '127.0.0.1', listen_port: 7890 };

function App() {
  const api = window.openProxy;
  const [cores, setCores] = useState([]);
  const [coreId, setCoreId] = useState('');
  const [profiles, setProfiles] = useState([]);
  const [profile, setProfile] = useState('');
  const [text, setText] = useState('{}');
  const [mode, setMode] = useState('form');
  const [status, setStatus] = useState({ state: 'stopped' });
  const [logs, setLogs] = useState([]);
  const [message, setMessage] = useState('');

  const parsed = useMemo(() => {
    try { return JSON.parse(text); } catch { return null; }
  }, [text]);

  const inbound = parsed?.inbounds?.[0] || blankInbound;
  const settings = parsed?.settings || { logLevel: 'info', allowLan: false };

  async function loadCores() {
    const result = await api.listCores();
    setCores(result);
    if (!coreId && result[0]) setCoreId(result[0].id);
  }

  async function loadProfiles(id) {
    if (!id) return;
    const result = await api.listProfiles(id);
    setProfiles(result);
    if (!result.includes(profile)) setProfile(result[0] || '');
  }

  async function loadProfile(id, name) {
    if (!id || !name) { setText('{}'); return; }
    setText(await api.readProfile(id, name));
  }

  useEffect(() => {
    loadCores();
    api.getStatus().then(setStatus);
    api.onLog((line) => setLogs((old) => [...old.slice(-499), line]));
    api.onStatus(setStatus);
  }, []);

  useEffect(() => { loadProfiles(coreId); }, [coreId]);
  useEffect(() => { loadProfile(coreId, profile); }, [coreId, profile]);

  function updateForm(field, value) {
    const next = parsed ? structuredClone(parsed) : {};
    next.inbounds = [{ ...blankInbound, ...(next.inbounds?.[0] || {}), [field]: value }];
    next.settings = { logLevel: 'info', allowLan: false, ...(next.settings || {}) };
    setText(JSON.stringify(next, null, 2));
  }

  function updateSettings(field, value) {
    const next = parsed ? structuredClone(parsed) : {};
    next.inbounds = next.inbounds || [blankInbound];
    next.settings = { logLevel: 'info', allowLan: false, ...(next.settings || {}), [field]: value };
    setText(JSON.stringify(next, null, 2));
  }

  async function run(action) {
    try {
      setMessage('');
      await action();
    } catch (error) {
      setMessage(error.message || String(error));
    }
  }

  async function save() {
    if (!parsed) throw new Error('JSON 格式不正确');
    await api.saveProfile(coreId, profile, text);
    setText(JSON.stringify(parsed, null, 2));
    setMessage('配置已保存');
  }

  async function createProfile() {
    const name = prompt('新配置文件名，例如 office.json');
    if (!name) return;
    const fileName = name.endsWith('.json') ? name : `${name}.json`;
    await api.createProfile(coreId, fileName, JSON.stringify({ inbounds: [blankInbound], settings: { logLevel: 'info', allowLan: false } }));
    await loadProfiles(coreId);
    setProfile(fileName);
  }

  async function removeProfile() {
    if (!profile || !confirm(`删除 ${profile}？`)) return;
    await api.deleteProfile(coreId, profile);
    await loadProfiles(coreId);
  }

  return (
    <div className="app-shell">
      <aside>
        <div className="brand">Open Proxy</div>
        <div className="muted">Electron MVP</div>
        <nav>
          <button className="nav active">代理控制</button>
          <button className="nav" onClick={() => setMode('form')}>表单配置</button>
          <button className="nav" onClick={() => setMode('text')}>文本编辑器</button>
        </nav>
      </aside>

      <main>
        <header>
          <div>
            <h1>代理核心控制台</h1>
            <p>选择 Core 与 Profile，编辑配置并启动进程。</p>
          </div>
          <span className={`status ${status.state}`}>{status.state === 'running' ? '运行中' : '已停止'}</span>
        </header>

        <section className="toolbar card">
          <label>Core<select value={coreId} onChange={(e) => setCoreId(e.target.value)}>{cores.map((c) => <option key={c.id}>{c.id}</option>)}</select></label>
          <label>Profile<select value={profile} onChange={(e) => setProfile(e.target.value)}>{profiles.map((p) => <option key={p}>{p}</option>)}</select></label>
          <button onClick={() => run(createProfile)}>新建</button>
          <button className="danger-ghost" onClick={() => run(removeProfile)}>删除</button>
          <div className="grow" />
          <button className="primary" disabled={!profile || status.state === 'running'} onClick={() => run(() => api.startCore(coreId, profile))}>启动</button>
          <button disabled={status.state !== 'running'} onClick={() => run(() => api.stopCore())}>停止</button>
        </section>

        <section className="workspace">
          <div className="card editor-card">
            <div className="tabs">
              <button className={mode === 'form' ? 'active-tab' : ''} onClick={() => setMode('form')}>UI 表单</button>
              <button className={mode === 'text' ? 'active-tab' : ''} onClick={() => setMode('text')}>JSON 文本</button>
              <div className="grow" />
              <button onClick={() => run(save)}>保存配置</button>
            </div>

            {mode === 'text' ? (
              <textarea value={text} onChange={(e) => setText(e.target.value)} spellCheck="false" />
            ) : (
              <div className="form-grid">
                <h3>Inbound</h3>
                <label>类型<select value={inbound.type} onChange={(e) => updateForm('type', e.target.value)}><option>mixed</option><option>http</option><option>socks</option></select></label>
                <label>标签<input value={inbound.tag || ''} onChange={(e) => updateForm('tag', e.target.value)} /></label>
                <label>监听地址<input value={inbound.listen || ''} onChange={(e) => updateForm('listen', e.target.value)} /></label>
                <label>监听端口<input type="number" value={inbound.listen_port || 0} onChange={(e) => updateForm('listen_port', Number(e.target.value))} /></label>
                <h3>用户 Settings</h3>
                <label>日志级别<select value={settings.logLevel || 'info'} onChange={(e) => updateSettings('logLevel', e.target.value)}><option>debug</option><option>info</option><option>warn</option><option>error</option></select></label>
                <label className="check"><input type="checkbox" checked={Boolean(settings.allowLan)} onChange={(e) => updateSettings('allowLan', e.target.checked)} />允许局域网连接</label>
              </div>
            )}
            {message && <div className="message">{message}</div>}
          </div>

          <div className="card log-card">
            <div className="log-header"><strong>运行日志</strong><button onClick={() => setLogs([])}>清空</button></div>
            <pre>{logs.length ? logs.join('') : '暂无日志。\n请将 Core 可执行文件放入 cores/<core>/bin/ 后启动。'}</pre>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
