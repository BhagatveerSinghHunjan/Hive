const { spawn, execFileSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const readline = require('node:readline');

function resolvePython(repoRoot) {
  if (process.env.HIVE_PYTHON) return process.env.HIVE_PYTHON;

  const venv = process.platform === 'win32'
    ? path.join(repoRoot, '.venv', 'Scripts', 'python.exe')
    : path.join(repoRoot, '.venv', 'bin', 'python');
  if (fs.existsSync(venv)) return venv;

  if (process.platform === 'win32') {
    try {
      const exe = execFileSync(
        'py',
        ['-3.13', '-c', 'import sys; print(sys.executable)'],
        { encoding: 'utf8', windowsHide: true, timeout: 10000 }
      ).trim();
      if (exe && fs.existsSync(exe)) return exe;
    } catch {
      // py launcher unavailable; fall through
    }
  }

  for (const candidate of ['python3', 'python']) {
    try {
      execFileSync(candidate, ['--version'], {
        encoding: 'utf8',
        windowsHide: true,
        timeout: 5000,
      });
      return candidate;
    } catch {
      // try the next interpreter
    }
  }

  return process.platform === 'win32' ? 'python' : 'python3';
}

class PythonBridge {
  constructor({ repoRoot, onEvent, onLog, onExit }) {
    this.repoRoot = repoRoot;
    this.onEvent = onEvent || (() => {});
    this.onLog = onLog || (() => {});
    this.onExit = onExit || (() => {});
    this.child = null;
    this.rl = null;
    this.command = null;
    this.stopping = false;
  }

  isRunning() {
    return Boolean(this.child) && !this.stopping;
  }

  start() {
    if (this.child) return;

    const python = resolvePython(this.repoRoot);
    this.command = `${python} -m hive.cli --server`;
    this.onLog(`[hive] starting: ${this.command}`);
    this.onLog(`[hive] cwd: ${this.repoRoot}`);

    let child;
    try {
      child = spawn(python, ['-m', 'hive.cli', '--server'], {
        cwd: this.repoRoot,
        windowsHide: true,
        env: {
          ...process.env,
          PYTHONUNBUFFERED: '1',
          PYTHONIOENCODING: 'utf-8',
        },
        stdio: ['pipe', 'pipe', 'pipe'],
      });
    } catch (err) {
      this.onExit({ code: -1, error: String(err) });
      return;
    }

    this.child = child;
    this.stopping = false;

    this.rl = readline.createInterface({ input: child.stdout });
    this.rl.on('line', (line) => {
      const trimmed = line.trim();
      if (!trimmed) return;
      try {
        this.onEvent(JSON.parse(trimmed));
      } catch {
        this.onLog(trimmed);
      }
    });

    child.stderr.on('data', (data) => {
      const text = data.toString('utf8');
      for (const line of text.split(/\r?\n/)) {
        const trimmed = line.trim();
        if (trimmed) this.onLog(trimmed);
      }
    });

    child.on('error', (err) => {
      this.onLog(`[hive] process error: ${err.message}`);
      this.cleanup();
      this.onExit({ code: -1, error: err.message });
    });

    child.on('exit', (code, signal) => {
      const wasStopping = this.stopping;
      this.cleanup();
      if (!wasStopping) {
        this.onExit({ code, signal });
      }
    });
  }

  send(msg) {
    if (!this.child || !this.child.stdin || !this.child.stdin.writable) {
      return false;
    }
    try {
      this.child.stdin.write(JSON.stringify(msg) + '\n');
      return true;
    } catch (err) {
      this.onLog(`[hive] send failed: ${err.message}`);
      return false;
    }
  }

  cleanup() {
    if (this.rl) {
      try {
        this.rl.close();
      } catch {
        // ignore
      }
      this.rl = null;
    }
    this.child = null;
  }

  async stop() {
    const child = this.child;
    if (!child) return;

    this.stopping = true;
    try {
      if (child.stdin && child.stdin.writable) {
        child.stdin.write(JSON.stringify({ type: 'quit' }) + '\n');
        child.stdin.end();
      }
    } catch {
      // ignore
    }

    await new Promise((resolve) => {
      let settled = false;
      const done = () => {
        if (settled) return;
        settled = true;
        resolve();
      };
      const timer = setTimeout(() => {
        try {
          child.kill();
        } catch {
          // ignore
        }
        done();
      }, 1200);

      child.once('exit', () => {
        clearTimeout(timer);
        done();
      });
    });

    this.cleanup();
    this.stopping = false;
  }

  destroy() {
    const child = this.child;
    if (!child) return;

    this.stopping = true;
    try {
      if (child.stdin && child.stdin.writable) {
        child.stdin.write(JSON.stringify({ type: 'quit' }) + '\n');
        child.stdin.end();
      }
    } catch {
      // ignore
    }

    const timer = setTimeout(() => {
      try {
        child.kill();
      } catch {
        // ignore
      }
    }, 300);
    if (typeof timer.unref === 'function') timer.unref();

    this.cleanup();
  }
}

module.exports = { PythonBridge, resolvePython };
