(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  let currentDraft = null;
  let currentPreview = null;
  let currentReply = null;
  let writableAccounts = [];
  const status = text => { $('result').textContent = text; };
  let approvalResolve = null;
  function finishApproval(approved) {
    $('confirmDialog').close();
    const resolve = approvalResolve;
    approvalResolve = null;
    if (resolve) resolve(approved);
  }
  $('confirmAccept').addEventListener('click', () => finishApproval(true));
  $('confirmCancel').addEventListener('click', () => finishApproval(false));
  $('confirmDialog').addEventListener('cancel', event => {
    event.preventDefault();
    finishApproval(false);
  });
  function askApproval(message) {
    if (approvalResolve) return Promise.resolve(false);
    $('confirmBody').textContent = message;
    $('confirmDialog').showModal();
    return new Promise(resolve => { approvalResolve = resolve; });
  }
  async function api(path, options = {}) {
    const token = $('token').value;
    if (!token) throw new Error('Webzugang eingeben');
    const response = await fetch('/api/mail/' + path, {
      ...options,
      headers: { 'Authorization': 'Bearer ' + token,
        ...(options.body ? { 'Content-Type': 'application/json' } : {}) }
    });
    if (!response.ok) throw new Error((await response.text()).slice(0, 180));
    return response.json();
  }
  const list = value => value.split(',').map(x => x.trim()).filter(Boolean);
  function item(container, lines, action) {
    const box = document.createElement('div'); box.className = 'item';
    for (const line of lines) {
      const p = document.createElement('p'); p.textContent = line; box.append(p);
    }
    if (action) box.append(action);
    container.append(box);
  }
  async function load() {
    const [statusData, notices, suggestions, moves] = await Promise.all([
      api('status'), api('notices'), api('suggestions'), api('moves')
    ]);
    status(statusData.accounts.length + ' aktive Postfächer');
    $('mailState').textContent = 'Verbunden';
    $('mailState').classList.add('connected');
    $('valAccounts').textContent = String(statusData.accounts.length);
    $('valUnread').textContent = String(statusData.accounts.reduce((sum, account) => sum + account.unread_inbox, 0));
    $('valNotices').textContent = String(statusData.accounts.reduce((sum, account) => sum + account.new_24h, 0));
    $('valSuggestions').textContent = String(suggestions.length);
    writableAccounts = Array.isArray(statusData.writable_accounts) ? statusData.writable_accounts : [];
    for (const select of document.querySelectorAll('select.writable-account')) {
      const previous = select.value;
      select.replaceChildren(...writableAccounts.map(account => new Option(account, account)));
      if (writableAccounts.includes(previous)) select.value = previous;
    }
    $('accounts').replaceChildren();
    for (const account of statusData.accounts)
      item($('accounts'), [account.account,
        account.new_24h + ' neu seit 24 h · ' + account.unread_inbox + ' ungelesen']);
    for (const account of statusData.unavailable)
      item($('accounts'), [account + ': derzeit nicht erreichbar']);
    $('notices').replaceChildren();
    if (!notices.length) item($('notices'), ['Keine neuen Meldungen']);
    for (const notice of notices) item($('notices'), [
      notice.account + ' · ' + notice.folder,
      notice.sender + ' · ' + notice.subject
    ]);
    $('suggestions').replaceChildren();
    if (!suggestions.length) item($('suggestions'), ['Keine offenen Vorschläge']);
    for (const suggestion of suggestions) {
      const button = document.createElement('button');
      button.textContent = 'Absender für Regel übernehmen';
      button.className = 'mail-button';
      button.addEventListener('click', () => {
        $('ruleAccount').value = suggestion.account;
        $('ruleSender').value = suggestion.sender;
        $('ruleFolder').focus();
      });
      item($('suggestions'), [suggestion.account + ' · ' + suggestion.sender,
        suggestion.subject + ' · ' + suggestion.reason], button);
    }
    $('moveHistory').replaceChildren();
    if (!moves.length) item($('moveHistory'), ['Noch keine Verschiebungen']);
    for (const move of moves) {
      const button = move.status === 'done' ? document.createElement('button') : null;
      if (button) {
        button.textContent = 'Rückgängig machen';
        button.className = 'mail-button';
        button.addEventListener('click', () => run(async () => {
          if (!await askApproval('Nachricht aus ' + move.target + ' zurück nach ' + move.source + ' verschieben?')) return;
          await api('moves/' + move.id + '/undo', { method: 'POST', body: '{}' });
          button.disabled = true;
          status('Verschiebung zurückgenommen');
        }));
      }
      item($('moveHistory'), [move.account + ' · UID ' + move.source_uid,
        move.source + ' → ' + move.target + ' · ' + move.status], button);
    }
  }
  async function attachment(file) {
    if (file.size > 8_000_000) throw new Error('Anhang zu groß: ' + file.name);
    const bytes = new Uint8Array(await file.arrayBuffer());
    let binary = '';
    for (let i = 0; i < bytes.length; i += 0x4000)
      binary += String.fromCharCode(...bytes.subarray(i, i + 0x4000));
    return { name: file.name, mime: file.type || 'application/octet-stream', data: btoa(binary) };
  }
  function showDraft(data) {
    const p = data.payload;
    $('reviewText').textContent = [
      'Von: ' + p.from, 'An: ' + p.to.join(', '),
      'Cc: ' + p.cc.join(', '), 'Bcc: ' + p.bcc.join(', '),
      'Betreff: ' + p.subject, '', p.body, '',
      'Anhänge: ' + (p.attachments.length ? p.attachments.map(a =>
        a.name + ' (' + a.mime + ', ' + Math.floor(a.data.length * 3 / 4) + ' Bytes)').join(', ') : 'keine')
    ].join('\n');
    $('review').hidden = false;
  }
  async function run(fn) { try { await fn(); } catch (e) { status(e.message); } }
  $('load').addEventListener('click', () => run(load));
  $('saveRule').addEventListener('click', () => run(async () => {
    const rule = { account: $('ruleAccount').value, sender: $('ruleSender').value,
      folder: $('ruleFolder').value };
    if (!await askApproval('Regel für ' + rule.sender + ' nach ' + rule.folder + ' freigeben?')) return;
    await api('rules', { method: 'POST', body: JSON.stringify(rule) });
    status('Regel freigegeben');
  }));
  $('readMessage').addEventListener('click', () => run(async () => {
    const params = new URLSearchParams({ account: $('readAccount').value,
      folder: $('readFolder').value, uid: $('readUid').value });
    const message = await api('message?' + params);
    currentReply = writableAccounts.includes(message.account) ? message : null;
    $('replyMessage').hidden = !currentReply;
    $('messageText').textContent = 'Von: ' + message.sender + '\nBetreff: ' +
      message.subject + '\n\n' + message.body;
    status('Nachricht geladen, Lesestatus unverändert');
  }));
  $('replyMessage').addEventListener('click', () => {
    if (!currentReply) return;
    $('from').value = currentReply.account;
    $('to').value = currentReply.sender;
    $('subject').value = /^Re:/i.test(currentReply.subject) ? currentReply.subject : 'Re: ' + currentReply.subject;
    $('body').focus();
    status('Antwort vorbereitet. Inhalt ergänzen und anschließend vollständig prüfen.');
  });
  $('createFolder').addEventListener('click', () => run(async () => {
    const body = { account: $('folderAccount').value, folder: $('folderName').value };
    if (!await askApproval('Ordner ' + body.folder + ' in ' + body.account + ' anlegen?')) return;
    await api('folders', { method: 'POST', body: JSON.stringify(body) });
    status('Ordner angelegt');
  }));
  $('preview').addEventListener('click', () => run(async () => {
    currentPreview = await api('previews', { method: 'POST', body: JSON.stringify({
      account: $('previewAccount').value, target: $('previewTarget').value }) });
    $('previewItems').replaceChildren();
    $('movedItems').replaceChildren();
    for (const message of currentPreview.items) {
      const label = document.createElement('label');
      const check = document.createElement('input');
      check.type = 'checkbox'; check.value = String(message.uid); check.style.width = 'auto';
      label.append(check, document.createTextNode(' ' + message.sender + ' · ' + message.subject +
        ' (UID ' + message.uid + ')'));
      $('previewItems').append(label);
    }
    $('approvePreview').hidden = currentPreview.items.length === 0;
    status(currentPreview.items.length + ' Treffer in der Vorschau');
  }));
  $('approvePreview').addEventListener('click', () => run(async () => {
    if (!currentPreview) throw new Error('Vorschau fehlt');
    const selected = [...$('previewItems').querySelectorAll('input:checked')].map(x => Number(x.value));
    if (!selected.length) throw new Error('Bitte konkrete Nachrichten auswählen');
    if (!await askApproval(selected.length + ' ausgewählte Nachrichten nach ' + currentPreview.target + ' verschieben?')) return;
    const result = await api('previews/' + currentPreview.id + '/approve', {
      method: 'POST', body: JSON.stringify({ selected_uids: selected }) });
    $('approvePreview').hidden = true;
    for (const moved of result.moved) {
      const button = document.createElement('button');
      button.textContent = 'Verschiebung ' + moved.id + ' zurücknehmen';
      button.className = 'mail-button';
      button.addEventListener('click', () => run(async () => {
        if (!await askApproval('Diese Verschiebung zurücknehmen?')) return;
        await api('moves/' + moved.id + '/undo', { method: 'POST', body: '{}' });
        button.disabled = true;
        status('Verschiebung zurückgenommen');
      }));
      item($('movedItems'), ['Verschoben nach ' + moved.target], button);
    }
    status(result.moved.length + ' verschoben, ' + result.unresolved_uids.length + ' ungeklärt');
  }));
  $('createDraft').addEventListener('click', () => run(async () => {
    const payload = { from: $('from').value, to: list($('to').value),
      cc: list($('cc').value), bcc: list($('bcc').value),
      subject: $('subject').value, body: $('body').value,
      attachments: await Promise.all([...$('attachments').files].map(attachment)) };
    if (currentReply) payload.reply_to_message = {
      account: currentReply.account, folder: currentReply.folder,
      uid: currentReply.uid, message_id: currentReply.message_id };
    const created = await api('drafts', { method: 'POST', body: JSON.stringify(payload) });
    currentDraft = await api('drafts/' + created.id);
    showDraft(currentDraft);
    status('Entwurf bereit zur Sichtprüfung');
  }));
  for (const id of ['from', 'to', 'cc', 'bcc', 'subject', 'body', 'attachments']) {
    $(id).addEventListener('input', () => {
      currentDraft = null;
      $('review').hidden = true;
      if (id === 'from' || id === 'to' || id === 'subject') currentReply = null;
    });
  }
  async function finish(path) {
    if (!currentDraft || currentDraft.status !== 'pending') throw new Error('Kein offener Entwurf');
    const message = path === 'send' ? 'Diese Nachricht jetzt senden?' : 'An Thunderbird übergeben?';
    if (!await askApproval(message)) return;
    const result = await api('drafts/' + currentDraft.id + '/' + path, {
      method: 'POST', body: JSON.stringify({ digest: currentDraft.digest }) });
    currentDraft.status = result.status;
    $('review').hidden = true;
    status('Entwurf: ' + result.status);
  }
  $('send').addEventListener('click', () => run(() => finish('send')));
  $('thunderbird').addEventListener('click', () => run(() => finish('thunderbird')));
})();
