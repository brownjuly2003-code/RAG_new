        (function() {
            'use strict';

            var apiBase = window.location.origin.replace(/\/+$/, '');
            var widgetTitle = 'Поддержка';
            var embedded = window.parent !== window;
            var parentOrigin = '';
            var handshakeComplete = false;
            var expectedNonce = '';
            var tenantId = 'default';
            var sessionId = '';
            var accessToken = '';
            var bootstrapPromise = null;
            var messages = document.getElementById('messages');
            var input = document.getElementById('input');
            var sendBtn = document.getElementById('sendBtn');
            var status = document.getElementById('status');
            var titleNode = document.getElementById('widgetTitle');
            var closeBtn = document.getElementById('closeBtn');
            var typingNode = null;
            var isSending = false;
            // As the web chat says it: the answer did not come in time, or did not come.
            var TIMEOUT_TEXT = 'Ответ не пришёл вовремя. Повторите вопрос или передайте его оператору.';
            var ERROR_TEXT = 'Не удалось получить ответ. Повторите вопрос или передайте его оператору.';
            var TICKET_ROUTES = ['human', 'error', 'error_escalation'];

            function isValidOrigin(value) {
                if (!value || value === 'null' || value === '*') {
                    return false;
                }
                try {
                    var parsed = new URL(value);
                    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
                } catch (err) {
                    return false;
                }
            }

            try {
                if (document.referrer) {
                    var refOrigin = new URL(document.referrer).origin;
                    if (isValidOrigin(refOrigin)) {
                        parentOrigin = refOrigin;
                    }
                }
            } catch (err) {
                parentOrigin = '';
            }

            function postToParent(message) {
                if (!embedded || !isValidOrigin(parentOrigin)) {
                    return;
                }
                window.parent.postMessage(message, parentOrigin);
            }

            function scheduleResize() {
                requestAnimationFrame(function() {
                    var scrollHeight = document.documentElement.scrollHeight || document.body.scrollHeight || 520;
                    postToParent({
                        type: 'rag-widget-resize',
                        height: Math.min(Math.max(scrollHeight, 420), 580)
                    });
                });
            }

            function updateTitle(nextTitle) {
                widgetTitle = nextTitle || widgetTitle;
                document.title = widgetTitle;
                titleNode.textContent = widgetTitle;
            }

            function setStatus(message, isError) {
                status.textContent = message || '';
                status.className = isError ? 'widget-status error' : 'widget-status';
                scheduleResize();
            }

            function autoSizeInput() {
                input.style.height = 'auto';
                input.style.height = Math.min(input.scrollHeight, 108) + 'px';
                scheduleResize();
            }

            function scrollMessages() {
                messages.scrollTop = messages.scrollHeight;
            }

            function addMessage(role, text) {
                var node = document.createElement('div');
                node.className = 'widget-msg ' + role;
                node.textContent = text;
                messages.appendChild(node);
                scrollMessages();
                scheduleResize();
                return node;
            }

            function addActionButton(row, className, label, onClick) {
                var button = document.createElement('button');
                button.type = 'button';
                button.className = 'widget-action ' + className;
                button.textContent = label;
                button.addEventListener('click', onClick);
                row.appendChild(button);
                return button;
            }

            // Retry and the operator under an answer that did not come; reason is the
            // ticket's, as /api/ask names its own: route=timeout or route=error.
            function addReplyActions(node, question, reason, withRetry) {
                var row = document.createElement('div');
                row.className = 'widget-actions';
                if (withRetry) {
                    addActionButton(row, 'widget-retry', 'Повторить', function() {
                        if (isSending) {
                            return;
                        }
                        node.remove();
                        input.value = question;
                        send();
                    });
                }
                if (reason) {
                    var escalateBtn = addActionButton(row, 'widget-escalate', 'Передать оператору', function() {
                        escalate(question, reason, row, escalateBtn);
                    });
                }
                node.appendChild(row);
                scrollMessages();
                scheduleResize();
            }

            // No automatic signal tells a bad answer from a good one on this Mac (PLAN.md
            // stage 3, outcome C): the client is told so under the answer and hands the
            // question over in one click; the ticket's reason is the answer's route.
            function addHandoverLine(node, question, reason) {
                var row = document.createElement('div');
                row.className = 'widget-handover';
                var note = document.createElement('span');
                note.textContent = 'Ответ составлен автоматически и может ошибаться.';
                row.appendChild(note);
                var button = document.createElement('button');
                button.type = 'button';
                button.className = 'widget-handover-btn';
                button.textContent = 'Передать оператору';
                button.addEventListener('click', function() {
                    escalate(question, reason, row, button);
                });
                row.appendChild(button);
                node.appendChild(row);
                scrollMessages();
                scheduleResize();
            }

            // A token expires (WIDGET_TOKEN_TTL_SEC) while a long answer runs: fetch a new
            // one for the same session once, then repeat the request.
            async function postWithToken(path, payload) {
                await ensureBootstrap();
                var response = await postJson(path, payload);
                if (response.status === 401) {
                    accessToken = '';
                    await ensureBootstrap();
                    response = await postJson(path, payload);
                }
                return response;
            }

            function postJson(path, payload) {
                return fetch(apiBase + path, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + accessToken
                    },
                    body: JSON.stringify(payload)
                });
            }

            async function escalate(question, reason, row, button) {
                button.disabled = true;
                setStatus('', false);
                try {
                    var response = await postWithToken('/api/escalate', {
                        session_id: sessionId,
                        question: question,
                        reason: reason
                    });
                    var data = await response.json().catch(function() {
                        return {};
                    });
                    if (!response.ok) {
                        throw new Error('escalate ' + response.status);
                    }
                    row.remove();
                    addMessage('assistant', data.message || 'Запрос передан оператору.');
                } catch (err) {
                    button.disabled = false;
                    setStatus('Не удалось передать вопрос оператору. Попробуйте ещё раз.', true);
                }
            }

            function setTyping(active) {
                if (active && !typingNode) {
                    typingNode = document.createElement('div');
                    typingNode.className = 'widget-msg assistant';
                    typingNode.innerHTML = '<div class="typing" aria-label="Ассистент печатает"><span></span><span></span><span></span></div>';
                    messages.appendChild(typingNode);
                    scrollMessages();
                    scheduleResize();
                    return;
                }

                if (!active && typingNode) {
                    typingNode.remove();
                    typingNode = null;
                    scheduleResize();
                }
            }

            async function ensureBootstrap() {
                if (accessToken && sessionId) {
                    return;
                }
                if (bootstrapPromise) {
                    return bootstrapPromise;
                }
                if (!isValidOrigin(parentOrigin) && embedded) {
                    throw new Error('Parent origin not established for widget bootstrap.');
                }
                var originForBootstrap = isValidOrigin(parentOrigin)
                    ? parentOrigin
                    : window.location.origin;

                bootstrapPromise = fetch(apiBase + '/api/widget/bootstrap', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        parent_origin: originForBootstrap,
                        tenant_id: tenantId,
                        session_id: sessionId || null,
                        handshake_nonce: expectedNonce || null
                    })
                }).then(function(response) {
                    return response.json().catch(function() {
                        return {};
                    }).then(function(data) {
                        if (!response.ok) {
                            var detail = data.detail || 'Widget bootstrap failed.';
                            throw new Error(typeof detail === 'string' ? detail : 'Widget bootstrap failed.');
                        }
                        accessToken = data.token || '';
                        sessionId = data.session_id || sessionId || '';
                        if (data.tenant_id) {
                            tenantId = String(data.tenant_id);
                        }
                        if (!accessToken) {
                            throw new Error('Widget token missing from bootstrap.');
                        }
                        postToParent({
                            type: 'rag-widget-bootstrapped',
                            sessionId: sessionId,
                            handshake_nonce: data.handshake_nonce || expectedNonce || null
                        });
                    });
                }).finally(function() {
                    bootstrapPromise = null;
                });
                return bootstrapPromise;
            }

            async function send() {
                var question = input.value.trim();
                if (!question || isSending) {
                    return;
                }

                isSending = true;
                sendBtn.disabled = true;
                setStatus('', false);
                addMessage('user', question);
                input.value = '';
                autoSizeInput();
                setTyping(true);

                var reply;
                try {
                    reply = await ask(question);
                } finally {
                    setTyping(false);
                    isSending = false;
                    sendBtn.disabled = false;
                    input.focus();
                }
                var node = addMessage('assistant', reply.text);
                if (reply.retry || reply.reason) {
                    addReplyActions(node, question, reply.reason, reply.retry);
                } else if (reply.handover) {
                    addHandoverLine(node, question, reply.handover);
                }
            }

            // What to show for a question: the answer, or what happened instead of it.
            async function ask(question) {
                try {
                    await ensureBootstrap();
                } catch (err) {
                    // Without a token nothing reached the service, the operator included.
                    setStatus(err && err.message ? err.message : 'Ошибка подключения. Попробуйте позже.', true);
                    return {
                        text: 'Не удалось подключиться к сервису. Попробуйте ещё раз чуть позже.',
                        reason: '',
                        retry: true
                    };
                }
                var response;
                try {
                    response = await postWithToken('/api/ask', {
                        question: question,
                        session_id: sessionId || null
                    });
                } catch (err) {
                    return { text: ERROR_TEXT, reason: 'route=error', retry: true };
                }
                var data = await response.json().catch(function() {
                    return {};
                });
                if (response.status === 504) {
                    // The request's wall-time limit (REQUEST_TIMEOUT_SEC) ran out.
                    return { text: TIMEOUT_TEXT, reason: 'route=timeout', retry: true };
                }
                if (!response.ok) {
                    return { text: ERROR_TEXT, reason: 'route=error', retry: true };
                }
                if (data.session_id) {
                    sessionId = String(data.session_id);
                }
                if (data.route === 'timeout') {
                    // The graph's own deadline: its apology, and /api/ask opens no ticket.
                    return { text: data.answer || TIMEOUT_TEXT, reason: 'route=timeout', retry: true };
                }
                // /api/ask opens the ticket itself on a human or error route; any other
                // answer offers the operator under it.
                var route = String(data.route || 'auto');
                var handover = TICKET_ROUTES.indexOf(route) === -1 ? 'route=' + route : '';
                return { text: data.answer || 'Нет ответа', reason: '', retry: false, handover: handover };
            }

            closeBtn.addEventListener('click', function() {
                postToParent({ type: 'rag-widget-close' });
            });

            sendBtn.addEventListener('click', send);

            input.addEventListener('input', autoSizeInput);
            input.addEventListener('keydown', function(event) {
                if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    send();
                }
            });

            window.addEventListener('message', function(event) {
                if (!event.data || typeof event.data !== 'object') {
                    return;
                }
                // Strict handshake: only known message types; origin must be http(s).
                if (!isValidOrigin(event.origin)) {
                    return;
                }
                if (handshakeComplete && parentOrigin && event.origin !== parentOrigin) {
                    return;
                }

                if (event.data.type === 'rag-widget-init') {
                    parentOrigin = event.origin;
                    handshakeComplete = true;
                    if (event.data.apiBase) {
                        apiBase = String(event.data.apiBase).replace(/\/+$/, '');
                    }
                    if (event.data.title) {
                        updateTitle(String(event.data.title));
                    }
                    if (event.data.tenantId || event.data.tenant_id) {
                        tenantId = String(event.data.tenantId || event.data.tenant_id);
                    }
                    if (event.data.sessionId || event.data.session_id) {
                        sessionId = String(event.data.sessionId || event.data.session_id);
                    }
                    if (event.data.handshake_nonce || event.data.nonce) {
                        expectedNonce = String(event.data.handshake_nonce || event.data.nonce);
                    }
                    if (event.data.isEmbedded) {
                        embedded = true;
                        closeBtn.hidden = false;
                    }
                    postToParent({
                        type: 'rag-widget-ack',
                        handshake_nonce: expectedNonce || null
                    });
                    scheduleResize();
                    ensureBootstrap().catch(function(err) {
                        setStatus(err && err.message ? err.message : 'Bootstrap failed', true);
                    });
                    return;
                }

                if (event.data.type === 'rag-widget-focus') {
                    if (!handshakeComplete && embedded) {
                        return;
                    }
                    input.focus();
                }
            });

            if (embedded) {
                closeBtn.hidden = false;
                postToParent({ type: 'rag-widget-ready' });
            }

            updateTitle(widgetTitle);
            autoSizeInput();
            scheduleResize();
            input.focus();
        })();
