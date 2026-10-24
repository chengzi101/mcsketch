import { test } from 'node:test';
import assert from 'node:assert/strict';
import {invalidate,snapshot,isCurrent,changeQuantity} from '../src/state.mjs';
import {quoteExpiry,latestOnly,expireQuote} from '../src/state.mjs';

test('old quote expiry does not discard a fresh in-flight quote for unchanged cart',()=>{
  const s={quote:{expires:10},plans:[1],revision:4};const version=snapshot(s);
  assert.equal(expireQuote(s,10),false);
  assert.equal(expireQuote(s,11),true);
  assert.equal(s.quote,null);assert.equal(s.plans,null);
  assert.equal(isCurrent(s,version),true);
  invalidate(s);assert.equal(isCurrent(s,version),false);
});
test('network delay never extends the official quote lifetime',()=>{const q={created_at:'2026-10-24T00:00:00Z',expires_in_seconds:120};assert.equal(quoteExpiry(q),Date.parse('2026-10-24T00:02:00Z'));assert.equal(quoteExpiry({}),0);});
test('late menu or category response is discarded after a new request',()=>{const gate=latestOnly();const first=gate.begin();const next=gate.begin();assert.equal(gate.current(first),false);assert.equal(gate.current(next),true);});
test('cart edits invalidate quote and discard late responses',()=>{const s={quote:{amount:10},plans:[1],revision:0};const v=snapshot(s);invalidate(s);assert.equal(s.quote,null);assert.equal(s.plans,null);assert.equal(isCurrent(s,v),false);});
test('quantity zero removes item without mutating original',()=>{const a={burger:1};assert.deepEqual(changeQuantity(a,'burger',-1),{});assert.deepEqual(a,{burger:1});});
