import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

test('desktop development proxy rejects remote or credential-bearing API targets', () => {
  const cwd=fileURLToPath(new URL('../',import.meta.url));
  for(const target of ['https://example.invalid','http://user:secret@127.0.0.1:8000','http://127.0.0.1:8000/unexpected']) {
    const result=spawnSync(process.execPath,['node_modules/vite/bin/vite.js','build'],{
      cwd,env:{...process.env,KILLCHAIN_DEV_API:target},encoding:'utf8',timeout:30000,
    });
    assert.equal(result.status,1);
    assert.match(result.stderr,/must be a loopback HTTP origin/);
  }
});
