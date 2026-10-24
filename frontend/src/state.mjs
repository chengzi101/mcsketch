export function invalidate(state) {state.quote=null;state.plans=null;state.revision++;}
export function snapshot(state) {return state.revision;}
export function isCurrent(state, revision) {return state.revision===revision;}
export function expireQuote(state, now=Date.now()) {
  if(!state.quote || now<=state.quote.expires)return false;
  // Expiry does not change cart/constraints. A fresh in-flight quote or repair
  // for the same revision must still be allowed to replace expired data.
  state.quote=null;state.plans=null;return true;
}
export function changeQuantity(cart,id,delta) {
  const copy={...cart};copy[id]=(copy[id]||0)+delta;if(copy[id]<=0)delete copy[id];return copy;
}
export function quoteExpiry(quote) {
  const created=Date.parse(quote.created_at);
  const ttl=Number(quote.expires_in_seconds);
  if(!Number.isFinite(created)||!Number.isFinite(ttl)||ttl<=0) return 0;
  return created+ttl*1000;
}
export function latestOnly() {
  let version=0;
  return {begin:()=>++version,current:(value)=>value===version};
}
