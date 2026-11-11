/* Navegación de lectura y respuestas acotadas; nunca ejecuta código del modelo. */
export const LORE_VIEWS=new Set(['resumen','alertas','territorio','conflictos','pais','fuentes','reportes','sistema']);
const norm=value=>String(value??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const list=value=>Array.isArray(value)?value:[];
const sourceKeys=['url','pdf_url','file_url','source_url'];
const caseIds=context=>new Set(list(context?.payload?.cases).map(c=>String(c.id)));
export function validateLoreAction(action,context={}){
  if(!action||typeof action!=='object'||Array.isArray(action))return null;
  if(action.type==='navigate'&&Object.keys(action).every(k=>['type','view'].includes(k))&&LORE_VIEWS.has(action.view))return {type:'navigate',view:action.view};
  if(action.type==='open_case'&&Object.keys(action).every(k=>['type','case_id'].includes(k))&&caseIds(context).has(String(action.case_id)))return {type:'open_case',case_id:String(action.case_id)};
  return null;
}
export function explicitLoreNavigation(question,context={}){
  const q=norm(question).trim().replace(/[¿?¡!.,;]+$/g,'');
  const match=/^(?:por favor[, ]+)?(?:abre|abrir|muestrame|muestra|ver|ve a|ir a|anda a|navega a|llevame a)\s+(.+)$/.exec(q);
  if(!match)return null;
  const requested=match[1].replace(/^(?:el|la|los|las|al|a)\s+/,'').trim();
  const aliases={resumen:'resumen',inicio:'resumen',alertas:'alertas','mis alertas':'alertas',mapa:'territorio',territorio:'territorio',conflictos:'conflictos','mis conflictos':'conflictos',casos:'conflictos',pais:'pais','conflictos del pais':'pais',fuentes:'fuentes',reportes:'reportes',reporte:'reportes','estado del sistema':'sistema',sistema:'sistema'};
  if(aliases[requested])return {action:{type:'navigate',view:aliases[requested]}};
  // Do not interpret compound instructions as an open-case command.
  if(/\b(?:envia|publica|borra|elimina|actualiza|alertas de| y )\b/.test(requested))return null;
  const words=requested.split(/\W+/).filter(w=>w.length>2&&!['caso','conflicto','del','los','las'].includes(w));
  const matches=list(context.payload?.cases).filter(c=>String(c.id)===requested||words.length&&words.every(w=>norm([c.name,c.district,c.province].join(' ')).includes(w)));
  if(matches.length===1)return {action:{type:'open_case',case_id:String(matches[0].id)},label:matches[0].name};
  return matches.length>1?{choices:matches.map(c=>({type:'open_case',case_id:String(c.id)}))}:null;
}
function sourceCatalog(context={}){
  const payload=context.payload||{},sources=[...list(payload.sources),...list(context.national?.cases),...list(payload.media?.items),...list(payload.documents)];
  for(const c of list(payload.cases))sources.push(...list(c.events));
  for(const alert of list(payload.alerts))sources.push(...list(alert.evidence));
  if(context.national?.source)sources.push({url:context.national.source,title:context.national.title});
  return sources;
}
function normalizedURL(value,base){try{const raw=String(value||'');if(!raw||raw.startsWith('#')||/[\\\u0000-\u0020]/.test(raw))return null;const url=new URL(raw,base);if(!['http:','https:'].includes(url.protocol)||url.username||url.password)return null;return url.href;}catch{return null;}}
export function validateLoreSource(source,context={}){
  if(!source||typeof source!=='object')return null;
  const base=context.baseURL||'http://127.0.0.1:8765/';
  const href=normalizedURL(source.url,base);if(!href)return null;
  const allowed=new Set();for(const item of sourceCatalog(context))for(const key of sourceKeys){const candidate=normalizedURL(item[key],base);if(candidate)allowed.add(candidate);}
  if(!allowed.has(href))return null;
  return {id:String(source.id||'').slice(0,80),title:String(source.title||source.institution||'Fuente incorporada').slice(0,400),url:href,locator:String(source.locator||'').slice(0,150),kind:String(source.kind||'fuente').slice(0,80)};
}
export function loreSourceMarkup(sources,context={}){
  const seen=new Set(),safe=list(sources).map(s=>validateLoreSource(s,context)).filter(s=>s&&!seen.has(s.url)&&seen.add(s.url));
  return safe.length?`<div class="lore-sources">${safe.map(s=>`<a class="lore-source-button" href="${esc(s.url)}" target="_blank" rel="noopener">${s.id?esc(s.id)+' · ':''}${esc(s.title)}${s.locator?' · '+esc(s.locator):''} ↗</a>`).join('')}</div>`:'';
}
export function loreActionMarkup(actions,context={}){
  return `<div class="lore-actions">${list(actions).map(a=>validateLoreAction(a,context)).filter(Boolean).map(action=>{const label=action.type==='navigate'?'Abrir '+action.view:'Abrir '+(context.payload.cases.find(c=>String(c.id)===action.case_id)?.name||'expediente');return `<button type="button" data-lore-action="${esc(JSON.stringify(action))}">${esc(label)}</button>`;}).join('')}</div>`;
}
export function loreCaseSources(c,context={}){
  const sources=[];
  for(const event of list(c?.events)){const source=list(context.payload?.sources).find(s=>s.id===event.source_id);const url=event.pdf_url||event.url||source?.url||source?.pdf_url;if(url)sources.push({id:event.source_id||'',title:source?.institution||event.title||'Evidencia del expediente',url,locator:event.literal&&event.page?'p. '+event.page:'',kind:event.literal?'pasaje PDF':'publicación'});}
  for(const id of list(c?.source_ids)){const source=list(context.payload?.sources).find(s=>s.id===id);if(source)sources.push({...source,url:source.url||source.pdf_url});}
  return loreSourceMarkup(sources.slice(0,8),context);
}
export function loreEvidenceAnswer(question,context={}){
  const q=norm(question);
  if(!/fuente|evidencia|cita|verifica|sustent/.test(q)||/de donde (salen|vienen) (los )?datos|de donde obtiene/.test(q))return null;
  const cases=list(context.payload?.cases),matches=cases.filter(c=>{const tokens=norm([c.name,c.district].join(' ')).split(/\W+/).filter(w=>w.length>3);return String(c.id)&&q.includes(String(c.id))||tokens.some(w=>q.includes(w));});
  const chosen=matches.length===1?matches[0]:!matches.length?cases.find(c=>String(c.id)===String(context.selectedCase)):null;
  if(!chosen){if(/acuerdo|compromiso|plazo|caso|afirmacion/.test(q))return `¿De qué expediente quieres consultar la evidencia?${loreActionMarkup(cases.slice(0,5).map(c=>({type:'open_case',case_id:String(c.id)})),context)}`;return null;}
  const literal=list(chosen.events).filter(event=>event.literal&&event.pdf_url&&event.page).slice(0,3);
  const quoteHTML=literal.map(event=>`<blockquote>«${esc(event.summary||'')}»</blockquote>`).join('');
  return `<b>Evidencia de ${esc(chosen.name)}</b><br>${literal.length?'Estos pasajes conservan un PDF y su página. Comprueba el alcance del texto antes de atribuir un compromiso.':'Estas son las publicaciones vinculadas al expediente. No tengo aquí un pasaje literal con página que acredite ese acuerdo específico.'}${quoteHTML}${loreCaseSources(chosen,context)}${loreActionMarkup([{type:'open_case',case_id:String(chosen.id)}],context)}`;
}
export function observedHistoryInYear(cases,year){const observed=[],unknown=[];for(const c of list(cases)){const periods=Array.isArray(c.observations)?c.observations.map(o=>o.period):Array.isArray(c.periods)?c.periods:null;if(!periods){unknown.push(c);continue;}if(periods.some(p=>String(p).startsWith(String(year)+'-')))observed.push(c);}return {observed,unknown};}
export function loreYearAnswer(question,context={}){
  const q=norm(question),year=(q.match(/\b20(?:1[2-9]|2[0-5])\b/)||[])[0];if(!year)return null;
  const history=context.national?.history;if(!history)return 'No tengo la serie histórica cargada para comprobar ese año.';
  const departments=Object.keys(history.departments||{}),department=departments.find(d=>q.includes(norm(d)));
  let cases=list(history.cases);if(department)cases=cases.filter(c=>norm(c.department)===norm(department));
  const company=(q.match(/antamina|bambas|petroper/)||[])[0];if(company)cases=cases.filter(c=>norm([c.companies,c.name].join(' ')).includes(company));
  if(!cases.length)return 'No tengo índices históricos de casos en esa selección para comprobar el año solicitado. No equivale a cero conflictos.';
  const {observed,unknown}=observedHistoryInYear(cases,year);
  const scope=department?' en '+esc(department):'';
  if(!unknown.length)return `Hay <b>${observed.length}</b> casos con una observación mensual incorporada en ${year}${scope}.${observed.length?' Algunos: '+observed.slice(0,5).map(c=>esc(c.name)).join('; ')+'.':''}<br>El conteo usa meses efectivamente registrados; no el intervalo entre la primera y última aparición.`;
  const monthly=department?list(history.departments[department]):list(history.series),rows=monthly.filter(row=>String(row.period).startsWith(year+'-'));
  return `No puedo calcular el número de conflictos distintos con observación en ${year}${scope} usando sólo este índice: ${unknown.length} casos no incluyen sus meses individuales. No los cuento por el intervalo entre primera y última aparición.${observed.length?` Sí hay ${observed.length} casos con meses explícitos de ese año.`:''}${rows.length?`<br>La serie disponible sí registra ${rows.length} meses de ${year}; sus conteos mensuales están entre ${Math.min(...rows.map(r=>r.total))} y ${Math.max(...rows.map(r=>r.total))}. Estos valores no se suman como casos únicos del año.`:''}${loreActionMarkup([{type:'navigate',view:'pais'}],context)}`;
}
export function loreStatusAnswer(question,context={}){
  const q=norm(question);if(!/cuant|cantidad|numero/.test(q)||!/(latente|activo|resuelto)/.test(q))return null;
  const requested=/latente/.test(q)?'Latente':/resuelto/.test(q)?'Resuelto':'Activo';
  const companyScope=/mis |tengo|mi cartera|mi empresa/.test(q)||context.payload?.company?.name&&q.includes(norm(context.payload.company.name));
  if(companyScope){const cases=list(context.payload?.cases).filter(c=>norm(c.status)===norm(requested));return `En los casos incorporados a tu cartera hay <b>${cases.length}</b> con estado ${esc(requested)} en ${esc(context.payload.period||'el corte disponible')}. Es la cobertura de la cartera, no el total de conflictos de la empresa.${loreActionMarkup([{type:'navigate',view:'conflictos'}],context)}`;}
  const national=context.national||{},all=list(national.cases),covered=list(national.coverage?.statuses);const known=covered.length?covered:[...new Set(all.map(c=>c.status).filter(Boolean))];if(!known.length)known.push('Activo');
  if(!known.some(status=>norm(status)===norm(requested)))return `La colección nacional disponible contiene fichas ${known.map(esc).join(', ')}. No dispongo de fichas ${esc(requested)} para responder ese conteo; no sería correcto responder cero.${loreActionMarkup([{type:'navigate',view:'pais'}],context)}`;
  const region=[...new Set(all.map(c=>c.region).filter(Boolean))].find(region=>q.includes(norm(region)));
  const cases=all.filter(c=>(!region||c.region===region)&&norm(c.status||'Activo')===norm(requested));
  return `El corte ${esc(national.period||'disponible')} incluye <b>${cases.length}</b> fichas con estado ${esc(requested)}${region?' en '+esc(region):' en el país'}.${loreSourceMarkup([{id:'DP',title:national.title||'Reporte de la Defensoría',url:national.source,kind:'reporte oficial'}],context)}${loreActionMarkup([{type:'navigate',view:'pais'}],context)}`;
}
export function renderLoreApiReply(response,context={}){
  const records=list(response?.records),body=records.length?records.map(record=>`<p>${esc(record.claim||'')}</p>${record.quote?`<details class="lore-quote"><summary>Ver cita literal</summary><blockquote>«${esc(record.quote)}»</blockquote></details>`:''}${loreSourceMarkup(list(response?.sources).filter(source=>String(source.id)===String(record.source_id)),context)}`).join(''):esc(response?.answer||'No obtuve una respuesta sustentada en esta selección.').replace(/\n/g,'<br>');
  return `${body}${records.length?'':loreSourceMarkup(response?.sources,context)}${loreActionMarkup(response?.actions,context)}<small class="lore-response-mode">${esc(response?.model||'Respuesta documental')} · revisa el alcance de las citas.</small>`;
}
