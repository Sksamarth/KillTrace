import {test} from 'node:test';
import assert from 'node:assert/strict';
import {scanMetrics} from '../src/scanMetrics.ts';

test('scan progress follows byte offsets without inventing completion',()=>{
  assert.equal(scanMetrics(50,100,20,2,'running').percent,50);
  assert.equal(scanMetrics(50,100,20,2,'failed').percent,50);
  assert.equal(scanMetrics(0,100,0,0,'hashing').percent,0);
  assert.equal(scanMetrics(0,0,0,0,'completed').percent,100);
});
test('scan metrics handle startup, bounds and rate honestly',()=>{
  assert.equal(scanMetrics(50,100,20,2,'running').rate,10);
  assert.equal(scanMetrics(0,100,0,0,'queued').rate,null);
  assert.equal(scanMetrics(101,100,20,2,'running').blocks,20);
  assert.equal(scanMetrics(-5,100,20,2,'running').blocks,0);
  assert.equal(scanMetrics(NaN,100,20,2,'running').percent,0);
});
