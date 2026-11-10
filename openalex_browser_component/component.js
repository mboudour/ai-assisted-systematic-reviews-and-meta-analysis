/* Streamlit v1 protocol, with no runtime dependencies. No credentials leave this
 * iframe except the Authorization header to the fixed OpenAlex endpoint. */
(() => {
  "use strict";

  const ENDPOINT = "https://api.openalex.org/works";
  const SELECT = "id,doi,title,publication_year,authorships,primary_location,abstract_inverted_index,cited_by_count,concepts,type,referenced_works";
  const TYPES = new Set(["article", "book-chapter", "conference-paper", "preprint", "review", "report"]);
  const input = document.getElementById("credentials");
  const run = document.getElementById("run");
  const clear = document.getElementById("clear");
  const status = document.getElementById("status");
  let settings = null;
  let settingsIdentity;
  let generation = 0;
  let active = null;

  function send(type, extra) {
    window.parent.postMessage({isStreamlitMessage: true, type, ...extra}, "*");
  }
  function height() {
    send("streamlit:setFrameHeight", {height: Math.ceil(document.documentElement.scrollHeight)});
  }
  function show(message, error = false) {
    status.textContent = message;
    status.className = error ? "error" : "";
    height();
  }
  function updateButton() {
    run.disabled = !settings || !input.files.length || active !== null;
  }
  function cancel() {
    generation += 1;
    if (active) active.abort();
    active = null;
    updateButton();
  }
  function validInteger(v, min, max) {
    return Number.isSafeInteger(v) && v >= min && v <= max;
  }
  function validateArgs(args) {
    if (!args || typeof args !== "object") return null;
    const {query, per_page, max_pages, year_from, year_to, publication_types,
      search_scope, require_abstract, config_id, config_revision} = args;
    if (typeof query !== "string" || !query.trim() ||
        !validInteger(per_page, 1, 100) || !validInteger(max_pages, 1, 5) ||
        (year_from !== null && !validInteger(year_from, 1, 9999)) ||
        (year_to !== null && !validInteger(year_to, 1, 9999)) ||
        (year_from !== null && year_to !== null && year_from > year_to) ||
        !Array.isArray(publication_types) || publication_types.length > TYPES.size ||
        publication_types.some(t => typeof t !== "string" || !TYPES.has(t)) ||
        new Set(publication_types).size !== publication_types.length ||
        !["title_abstract_exact", "broad"].includes(search_scope) ||
        typeof require_abstract !== "boolean" ||
        typeof config_id !== "string" || !/^[0-9a-f]{64}$/.test(config_id) ||
        !validInteger(config_revision, 0, Number.MAX_SAFE_INTEGER)) return null;
    // Take only the known fields; no message-provided URL or headers are used.
    return {query, per_page, max_pages, year_from, year_to,
      publication_types: [...publication_types], search_scope, require_abstract,
      config_id, config_revision};
  }
  window.addEventListener("message", (event) => {
    if (event.source !== window.parent || !event.data || event.data.type !== "streamlit:render") return;
    const next = validateArgs(event.data.args);
    const identity = next ? JSON.stringify(next) : null;
    if (identity !== settingsIdentity || (!next && settings)) {
      cancel();
      settings = next;
      settingsIdentity = identity;
      if (!next) show("Invalid search settings. No request was sent.", true);
      else show("Search settings ready. Choose a file and select Run Search; settings changes require a new search.");
    }
    updateButton();
    height();
  });
  input.addEventListener("click", () => {
    // Even selecting the same file (which may not fire change) cancels a run.
    if (active) {
      cancel();
      show("File selection cancelled the current search. Select Run Search to start again.");
    }
  });
  input.addEventListener("change", () => {
    cancel();
    show(input.files.length ? "File selected locally. Select Run Search to continue." : "File removed. Choose a file to search.");
    updateButton();
  });
  clear.addEventListener("click", () => {
    cancel();
    input.value = "";
    show("File removed. Choose a file to search.");
    updateButton();
  });

  function containsSecrets(text, apiKey, email) {
    if (typeof text !== "string") return false;
    const lower = text.toLowerCase();
    return [apiKey, email].some(secret => lower.includes(secret.toLowerCase()));
  }
  function containsCredentialLike(text) {
    return /\b(?:api[_-]?key|authorization|access[_-]?token)\s*[:=]\s*\S+|\bbearer\s+\S+/i.test(text);
  }
  function checkOutput(value, apiKey, email) {
    if (typeof value === "string") return !containsSecrets(value, apiKey, email) && !containsCredentialLike(value);
    if (Array.isArray(value)) return value.every(item => checkOutput(item, apiKey, email));
    if (value && typeof value === "object") {
      return Object.entries(value).every(([k, v]) => !containsSecrets(k, apiKey, email) &&
        !containsCredentialLike(k) && checkOutput(v, apiKey, email));
    }
    return true;
  }
  function safeText(v) {
    if (v !== null && typeof v !== "string") throw new Error("bad data");
    return v;
  }
  function safeNumber(v) {
    if (v !== null && !validInteger(v, 0, Number.MAX_SAFE_INTEGER)) throw new Error("bad data");
    return v;
  }
  function isObject(v) { return v !== null && typeof v === "object" && !Array.isArray(v); }
  function projectObject(v, mapping) {
    if (v === null) return null;
    if (!isObject(v)) throw new Error("bad data");
    const out = Object.create(null);
    for (const [field, transform] of Object.entries(mapping)) {
      if (Object.prototype.hasOwnProperty.call(v, field)) out[field] = transform(v[field]);
    }
    return out;
  }
  function arrayOf(v, transform) {
    if (v === null) return null;
    if (!Array.isArray(v)) throw new Error("bad data");
    return v.map(transform);
  }
  function projectAbstract(v) {
    if (v === null) return null;
    if (!isObject(v)) throw new Error("bad data");
    const out = Object.create(null);
    for (const [word, positions] of Object.entries(v)) {
      if (!Array.isArray(positions)) throw new Error("bad data");
      out[word] = positions.map(safeNumber);
    }
    return out;
  }
  function projectWork(v) {
    const displayName = item => projectObject(item, {display_name: safeText});
    return projectObject(v, {
      id: safeText, doi: safeText, title: safeText, publication_year: safeNumber,
      authorships: a => arrayOf(a, item => projectObject(item, {author: displayName})),
      primary_location: loc => projectObject(loc, {source: displayName}),
      abstract_inverted_index: projectAbstract,
      cited_by_count: safeNumber,
      concepts: c => arrayOf(c, displayName),
      type: safeText,
      referenced_works: refs => arrayOf(refs, safeText)
    });
  }
  function getFilters(config) {
    const filters = [];
    if (config.year_from !== null) filters.push(`from_publication_date:${String(config.year_from).padStart(4, "0")}-01-01`);
    if (config.year_to !== null) filters.push(`to_publication_date:${String(config.year_to).padStart(4, "0")}-12-31`);
    if (config.publication_types.length) filters.push(`type:${config.publication_types.join("|")}`);
    if (config.require_abstract) filters.push("has_abstract:true");
    return filters;
  }
  function randomId() {
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    return Array.from(bytes, n => n.toString(16).padStart(2, "0")).join("");
  }
  function current(controller, version) {
    return active === controller && !controller.signal.aborted && generation === version;
  }

  run.addEventListener("click", async () => {
    if (!settings || !input.files.length || active) return;
    const config = settings;
    const file = input.files[0];
    const controller = new AbortController();
    const version = generation;
    active = controller;
    updateButton();
    let timedOut = false;
    try {
      if (file.size > 65536) {
        show("Credentials file is too large; choose a small JSON file.", true);
        return;
      }
      let credentials;
      try { credentials = JSON.parse(await file.text()); }
      catch (_) {
        if (current(controller, version)) show("The credentials file is not valid JSON.", true);
        return;
      }
      if (!current(controller, version)) return;
      if (!isObject(credentials) || typeof credentials.api_key !== "string" ||
          !/^[\x21-\x7e]+$/.test(credentials.api_key) ||
          typeof credentials.email !== "string" ||
          !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(credentials.email)) {
        show("The JSON must contain a nonempty api_key and a valid email.", true);
        return;
      }
      // These values are local to this click; the email is used only for leakage checks.
      const apiKey = credentials.api_key;
      const email = credentials.email;
      const filters = getFilters(config);
      const searchParam = config.search_scope === "broad" ? "search" : "search.title_and_abstract.exact";
      const records = [];
      const seen = new Set();
      let cursor = "*";
      let total = null;
      let pages = 0;
      let possiblyTruncated = false;
      for (let page = 1; page <= config.max_pages; page += 1) {
        if (!current(controller, version)) return;
        const params = new URLSearchParams();
        params.set(searchParam, config.query);
        params.set("per-page", String(config.per_page));
        params.set("cursor", cursor);
        params.set("select", SELECT);
        if (filters.length) params.set("filter", filters.join(","));
        // Check both decoded values and the serialized URL, including cursors from an untrusted response.
        const url = `${ENDPOINT}?${params.toString()}`;
        if ([...params.values()].some(v => containsSecrets(v, apiKey, email)) ||
            containsSecrets(url, apiKey, email) ||
            [apiKey, email].some(s => url.toLowerCase().includes(encodeURIComponent(s).toLowerCase()))) {
          show("Search settings or pagination contain private credentials; no results were sent. Change the settings and try again.", true);
          return;
        }
        seen.add(cursor);
        show(`Contacting OpenAlex: page ${page} of up to ${config.max_pages}…`);
        const timer = setTimeout(() => {
          if (!current(controller, version)) return;
          timedOut = true;
          controller.abort();
          show("OpenAlex request timed out. No results were sent.", true);
        }, 30000);
        let response;
        let payload;
        try {
          response = await fetch(url, {
            method: "GET", headers: {Authorization: `Bearer ${apiKey}`},
            mode: "cors", credentials: "omit", cache: "no-store", redirect: "error",
            referrerPolicy: "no-referrer", signal: controller.signal
          });
          if (!current(controller, version)) return;
          if (!response.ok) {
            const code = response.status;
            if (code === 401 || code === 403) show(`OpenAlex authentication or authorization failed (HTTP ${code}). No results were sent.`, true);
            else if (code === 429) show("OpenAlex rate limit exceeded (HTTP 429). Try again later; no results were sent.", true);
            else show(`OpenAlex request failed (HTTP ${Number.isInteger(code) ? code : "error"}). No results were sent.`, true);
            return;
          }
          payload = await response.json();
        } finally { clearTimeout(timer); }
        if (!current(controller, version)) return;
        if (!isObject(payload) || !Array.isArray(payload.results) || payload.results.length > config.per_page ||
            !isObject(payload.meta)) throw new Error("bad data");
        if (page === 1) {
          const count = payload.meta.count;
          if (count !== undefined && count !== null && !validInteger(count, 0, Number.MAX_SAFE_INTEGER)) throw new Error("bad data");
          total = count === undefined ? null : count;
        }
        const batch = payload.results.map(projectWork);
        if (batch.some(item => item === null)) throw new Error("bad data");
        records.push(...batch);
        pages += 1;
        const next = payload.meta.next_cursor;
        if (next !== undefined && next !== null && (typeof next !== "string" || next.length > 8192)) throw new Error("bad data");
        if (!batch.length || !next) break;
        if (seen.has(next)) {
          show("OpenAlex returned a repeated pagination cursor. No results were sent.", true);
          return;
        }
        if (page === config.max_pages) { possiblyTruncated = true; break; }
        cursor = next;
      }
      if (!current(controller, version)) return;
      if (total !== null && total > records.length) possiblyTruncated = true;
      const metadata = {
        request_id: randomId(), config_id: config.config_id, config_revision: config.config_revision,
        query: config.query, endpoint: ENDPOINT, search_param: searchParam, scope: config.search_scope,
        filters, filter: filters.join(","), returned_total: total, total_matches: total,
        pages, pages_fetched: pages, returned: records.length, records_retrieved: records.length,
        per_page: config.per_page, max_pages: config.max_pages,
        fetched_at_utc: new Date().toISOString(), possibly_truncated: possiblyTruncated
      };
      const value = {records, metadata};
      if (!checkOutput(value, apiKey, email) || containsSecrets(JSON.stringify(value), apiKey, email)) {
        show("The response contains private or credential-like data; no results were sent.", true);
        return;
      }
      send("streamlit:setComponentValue", {value, dataType: "json"});
      show(`Search complete: ${records.length} records from ${pages} page${pages === 1 ? "" : "s"} sent to the app.`);
    } catch (_) {
      if (timedOut && generation === version) show("OpenAlex request timed out. No results were sent.", true);
      else if (current(controller, version)) show("OpenAlex request failed or returned invalid data. No results were sent.", true);
    } finally {
      if (active === controller) active = null;
      updateButton();
    }
  });

  send("streamlit:componentReady", {apiVersion: 1});
  height();
  if (typeof ResizeObserver !== "undefined") new ResizeObserver(height).observe(document.body);
})();
