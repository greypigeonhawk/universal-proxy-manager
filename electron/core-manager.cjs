const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');

class CoreManager {
  constructor(rootDir, emitLog, emitStatus) {
    this.rootDir = rootDir;
    this.coresDir = path.join(rootDir, 'cores');
    this.emitLog = emitLog;
    this.emitStatus = emitStatus;
    this.process = null;
    this.running = null;
  }

  safeCoreDir(coreId) {
    const target = path.resolve(this.coresDir, coreId);
    if (!target.startsWith(path.resolve(this.coresDir) + path.sep)) throw new Error('Invalid core id');
    return target;
  }

  safeProfilePath(coreId, fileName) {
    if (path.basename(fileName) !== fileName || !fileName.endsWith('.json')) throw new Error('Invalid profile name');
    const target = path.resolve(this.safeCoreDir(coreId), 'config', fileName);
    const configDir = path.resolve(this.safeCoreDir(coreId), 'config');
    if (!target.startsWith(configDir + path.sep)) throw new Error('Invalid profile path');
    return target;
  }

  listCores() {
    if (!fs.existsSync(this.coresDir)) return [];
    return fs.readdirSync(this.coresDir, { withFileTypes: true })
      .filter((entry) => entry.isDirectory())
      .map((entry) => {
        const descriptorPath = path.join(this.coresDir, entry.name, 'core.json');
        if (!fs.existsSync(descriptorPath)) return null;
        const descriptor = JSON.parse(fs.readFileSync(descriptorPath, 'utf8'));
        return { id: entry.name, ...descriptor };
      })
      .filter(Boolean);
  }

  listProfiles(coreId) {
    const dir = path.join(this.safeCoreDir(coreId), 'config');
    fs.mkdirSync(dir, { recursive: true });
    return fs.readdirSync(dir).filter((name) => name.endsWith('.json')).sort();
  }

  readProfile(coreId, fileName) {
    return fs.readFileSync(this.safeProfilePath(coreId, fileName), 'utf8');
  }

  saveProfile(coreId, fileName, content, mustBeNew = false) {
    JSON.parse(content);
    const target = this.safeProfilePath(coreId, fileName);
    if (mustBeNew && fs.existsSync(target)) throw new Error('Profile already exists');
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, `${JSON.stringify(JSON.parse(content), null, 2)}\n`, 'utf8');
    return true;
  }

  deleteProfile(coreId, fileName) {
    const target = this.safeProfilePath(coreId, fileName);
    if (this.running?.coreId === coreId && this.running?.fileName === fileName) throw new Error('Stop the core before deleting its active profile');
    fs.unlinkSync(target);
    return true;
  }

  descriptor(coreId) {
    return JSON.parse(fs.readFileSync(path.join(this.safeCoreDir(coreId), 'core.json'), 'utf8'));
  }

  start(coreId, fileName) {
    if (this.process) throw new Error('A core is already running');
    const descriptor = this.descriptor(coreId);
    const coreDir = this.safeCoreDir(coreId);
    const profilePath = this.safeProfilePath(coreId, fileName);
    const executable = path.resolve(coreDir, descriptor.executable);
    if (!fs.existsSync(executable)) throw new Error(`Core executable not found: ${descriptor.executable}`);
    const args = descriptor.startArgs.map((arg) => arg.replace('{config}', profilePath));

    this.process = spawn(executable, args, { cwd: coreDir, windowsHide: true });
    this.running = { coreId, fileName, pid: this.process.pid, startedAt: Date.now() };
    this.emitStatus(this.status());
    this.emitLog(`[Open Proxy] Started ${coreId} with ${fileName}`);

    this.process.stdout.on('data', (data) => this.emitLog(data.toString()));
    this.process.stderr.on('data', (data) => this.emitLog(data.toString()));
    this.process.on('error', (error) => this.emitLog(`[Core error] ${error.message}`));
    this.process.on('exit', (code, signal) => {
      this.emitLog(`[Open Proxy] Core exited (code=${code}, signal=${signal || 'none'})`);
      this.process = null;
      this.running = null;
      this.emitStatus(this.status());
    });
    return this.status();
  }

  stop() {
    if (!this.process) return this.status();
    this.process.kill('SIGTERM');
    const processToKill = this.process;
    setTimeout(() => {
      if (this.process === processToKill) processToKill.kill('SIGKILL');
    }, 3000);
    return this.status();
  }

  status() {
    return this.running ? { state: 'running', ...this.running } : { state: 'stopped' };
  }
}

module.exports = { CoreManager };
