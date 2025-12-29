/**
 * Insta Outreach Logger - Content Script (v13 - Sequential UI & Manual Logging)
 */

console.log('[InstaLogger] Content Script Loaded (v13)');

// =============================================================================
// Globals & State
// =============================================================================
const CHAT_INPUT_SELECTOR = 'div[role="textbox"][aria-label="Message"]';
const ACTOR_CHECK_INTERVAL = 5000;

let activeChatInput = null;
let lastCheckedUrl = '';
let lastCheckedUsername = '';
let isCheckInProgress = false;
let bannerPulseInterval = null;
let actorCheckInterval = null;
let currentActorUsername = null;
let cachedActors = []; 

// Port connection
let port = null;
let pendingCallbacks = new Map();
let messageIdCounter = 0;

function connectPort() {
    if (!chrome.runtime?.id) return; // Context invalidated
    try {
        port = chrome.runtime.connect({ name: 'content-script' });
        port.onMessage.addListener((message) => {
            if (message.type === 'SYNC_COMPLETED') {
                fetchCachedActors();
                if (lastCheckedUsername && document.visibilityState === 'visible') {
                    runProfileCheck(lastCheckedUsername, true);
                }
                return;
            }
            if (message.requestId && pendingCallbacks.has(message.requestId)) {
                const callback = pendingCallbacks.get(message.requestId);
                pendingCallbacks.delete(message.requestId);
                callback(message);
            }
        });
        port.onDisconnect.addListener(() => {
            port = null;
            setTimeout(connectPort, 1000);
        });
    } catch (e) {
        console.error('[InstaLogger] Failed to connect port:', e);
    }
}

function fetchCachedActors() {
    sendMessageToBackground({ type: 'GET_ALL_ACTORS' }, (response) => {
        if (response?.success && response?.data?.actors) {
            cachedActors = response.data.actors;
        }
    });
}

function sendMessageToBackground(data, callback) {
    if (!chrome.runtime?.id) return; // Context invalidated
    if (!port) connectPort();
    if (!port) return; // Still no port?
    try {
        if (callback) {
            const requestId = ++messageIdCounter;
            data.requestId = requestId;
            pendingCallbacks.set(requestId, callback);
        }
        port.postMessage(data);
    } catch (e) {
        console.error('[InstaLogger] Error sending message:', e);
        if (callback) callback({ error: true, message: e.message });
    }
}

// =============================================================================
// 1. Discovery & Actor Logic
// =============================================================================

function scrapeProfileData(username) {
    // Safety check: Ensure we are still on the correct profile page
    if (!window.location.href.includes(username)) {
        return null;
    }

    try {
        let fullName = "";
        
        // Strategy A: Open Graph Title
        const ogTitle = document.querySelector('meta[property="og:title"]')?.content;
        if (ogTitle && ogTitle.includes(`@${username}`)) {
            const match = ogTitle.match(/^(.*?) \(@/);
            if (match) fullName = match[1];
        }

        // Strategy B: Page Title
        if (!fullName) {
            const titleMatch = document.title.match(/^(.*?) \(@/);
            if (titleMatch) fullName = titleMatch[1];
        }

        // Strategy C: H1 Header
        if (!fullName) {
            const h1 = document.querySelector('header h1');
            if (h1) fullName = h1.innerText;
        }
        
        if (fullName && /^\d+/.test(fullName)) {
             const headerHeaders = document.querySelectorAll('header h2');
             for (const h2 of headerHeaders) {
                 if (h2.innerText.length > 2) {
                     fullName = h2.innerText; 
                     break;
                 }
             }
        }

        // Bio Scraping
        let bioText = "";
        let externalLink = "";
        const header = document.querySelector('header');
        if (header) {
            const linkEl = header.querySelector('a[rel*="nofollow"]');
            if (linkEl) externalLink = linkEl.href;
            bioText = header.innerText; 
        }
        
        const ogDesc = document.querySelector('meta[property="og:description"]')?.content;
        if (!bioText && ogDesc) bioText = ogDesc;

        if (fullName || bioText || externalLink) {
            return {
                fullName: fullName,
                bio: bioText ? bioText.substring(0, 1000) : "", // Increased limit
                externalLink: externalLink,
                timestamp: Date.now()
            };
        }
    } catch (e) {
        console.error("[InstaLogger] Scraping failed:", e);
    }
    return null;
}

function cacheProfile(username) {
    const data = scrapeProfileData(username);
    if (data) {
        chrome.storage.local.get('profileCache', (res) => {
            const cache = res.profileCache || {};
            cache[username] = data;
            chrome.storage.local.set({ profileCache: cache });
            console.log(`[InstaLogger] Cached data for ${username}:`, data);
        });
    }
}

function scrapeCurrentViewerUsername() {
    const profileLinks = Array.from(document.querySelectorAll('a[href^="/"]'));
    for (const link of profileLinks) {
        const href = link.getAttribute('href');
        if (!href) continue;
        const hasProfileImg = link.querySelector('img[alt*="profile" i]') || link.querySelector('img[data-testid="user-avatar"]');
        if (hasProfileImg) {
            const match = href.match(/^\/([a-zA-Z0-9_.]+)\/?$/);
            if (match && match[1] && !['explore', 'reels', 'inbox', 'direct', 'accounts', 'p'].includes(match[1])) return match[1];
        }
        if (link.textContent.trim().toLowerCase() === 'profile') {
            const match = href.match(/^\/([a-zA-Z0-9_.]+)\/?$/);
            if (match && match[1]) return match[1];
        }
    }
    return null;
}

async function handleActorSwitch(newUsername) {
    currentActorUsername = newUsername;
    await chrome.storage.local.set({ actorUsername: newUsername });
    sendMessageToBackground({ type: 'ACTOR_SWITCH', payload: { old_actor: currentActorUsername, new_actor: newUsername } });
    if (lastCheckedUsername && !isCheckInProgress) runProfileCheck(lastCheckedUsername, true);
}

async function checkForActorSwitch() {
    let storedUsername;
    try {
        const stored = await chrome.storage.local.get('actorUsername');
        storedUsername = stored.actorUsername;
    } catch (e) {
        if (e.message.includes('context invalidated')) {
            if (actorCheckInterval) clearInterval(actorCheckInterval);
            return;
        }
        return;
    }
    const scrapedUsername = scrapeCurrentViewerUsername();
    if (!scrapedUsername) {
        if (!storedUsername) sendMessageToBackground({ type: 'REQUEST_ACTOR_DISCOVERY' });
        return;
    }
    if (!currentActorUsername && storedUsername) currentActorUsername = storedUsername;
    if (storedUsername && scrapedUsername !== storedUsername) await handleActorSwitch(scrapedUsername);
    else if (!storedUsername && scrapedUsername) {
        currentActorUsername = scrapedUsername;
        await chrome.storage.local.set({ actorUsername: scrapedUsername });
        sendMessageToBackground({ type: 'FOUND_ACTOR_USERNAME', username: scrapedUsername });
    }
}

function startActorVerification() {
    if (actorCheckInterval) clearInterval(actorCheckInterval);
    setTimeout(checkForActorSwitch, 1000);
    actorCheckInterval = setInterval(checkForActorSwitch, ACTOR_CHECK_INTERVAL);
}

// =============================================================================
// 2. UI & Banner Logic
// =============================================================================

function makeDraggable(element) {
    let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
    function dragMouseDown(e) {
        if (e.target.closest('.close-btn') || e.target.closest('.status-dropdown-wrapper') || 
            e.target.closest('.notes-container') || e.target.closest('.manual-form')) return;
        e.preventDefault();
        pos3 = e.clientX; pos4 = e.clientY;
        document.addEventListener('mouseup', closeDragElement);
        document.addEventListener('mousemove', elementDrag);
    }
    function elementDrag(e) {
        e.preventDefault();
        pos1 = pos3 - e.clientX; pos2 = pos4 - e.clientY;
        pos3 = e.clientX; pos4 = e.clientY;
        let newTop = element.offsetTop - pos2;
        let newLeft = element.offsetLeft - pos1;
        element.style.top = newTop + "px";
        element.style.left = newLeft + "px";
        element.style.right = ''; element.style.transform = '';
    }
    function closeDragElement() {
        document.removeEventListener('mouseup', closeDragElement);
        document.removeEventListener('mousemove', elementDrag);
        chrome.storage.local.set({ bannerPosition: { top: element.style.top, left: element.style.left } });
    }
    element.addEventListener('mousedown', dragMouseDown);
}

function startBannerPulse(banner, r, g, b) {
    if (bannerPulseInterval) clearInterval(bannerPulseInterval);
    let isPulsed = false;
    bannerPulseInterval = setInterval(() => {
        if (!banner || !document.body.contains(banner)) { clearInterval(bannerPulseInterval); return; }
        banner.style.boxShadow = isPulsed ? `0 0 8px rgba(${r}, ${g}, ${b}, 0.4)` : `0 0 25px rgba(${r}, ${g}, ${b}, 1.0)`;
        isPulsed = !isPulsed;
    }, 600);
}

function stopBannerPulse() {
    if (bannerPulseInterval) { clearInterval(bannerPulseInterval); bannerPulseInterval = null; }
}

function updateSyncStage(banner, stage) {
    if (!banner) return;
    stopBannerPulse();
    banner.style.boxShadow = '';
    const allStages = ['sync-stage-local', 'sync-stage-cloud', 'sync-stage-downloading', 'sync-stage-complete', 'sync-stage-not-found', 'sync-stage-error', 'sync-stage-detection-failed', 'sync-stage-excluded'];
    banner.classList.remove(...allStages);
    if (stage) {
        banner.classList.add(`sync-stage-${stage}`);
        if (stage === 'local') startBannerPulse(banner, 245, 158, 11);
        else if (stage === 'downloading') startBannerPulse(banner, 16, 185, 129);
        else if (stage === 'error') startBannerPulse(banner, 239, 68, 68);
        else if (stage === 'detection-failed') startBannerPulse(banner, 255, 69, 0);
    }
}

function updateDropdownSyncStage(dropdown, stage) {
    if (!dropdown) return;
    dropdown.classList.remove('status-sync-local', 'status-sync-queued', 'status-sync-synced', 'status-sync-error');
    if (stage) dropdown.classList.add(`status-sync-${stage}`);
}

function formatDate(isoString) {
    if (!isoString || isoString === 'null' || isoString === 'None') return 'Unknown Date';
    try {
        const date = new Date(isoString);
        if (isNaN(date.getTime())) return 'Unknown Date';
        return date.toLocaleDateString('en-US', { day: 'numeric', month: 'long' });
    } catch (e) { return 'Unknown Date'; }
}

async function showStatusBanner(state, data = {}) {
    document.querySelectorAll('.insta-warning-banner').forEach(b => b.remove());

    const isExcluded = data.status === 'Excluded';
    const banner = document.createElement('div');
    banner.id = 'insta-warning-banner';
    banner.className = 'insta-warning-banner';
    banner.dataset.state = isExcluded ? 'excluded' : state;

    if (data.syncStage) {
        banner.classList.add(`sync-stage-${data.syncStage}`);
        if(data.syncStage === 'detection-failed') startBannerPulse(banner, 255, 69, 0);
    }

    let isDraggable = false;
    const isContacted = state === 'contacted';
    
    let statusOptions = [];
    if (isExcluded) {
        statusOptions = [
            { label: 'Not Contacted Before', value: 'FLIP_TO_NOT_CONTACTED' },
            { label: 'Contacted Before', value: 'FLIP_TO_CONTACTED' }
        ];
    } else {
        statusOptions = [
            { label: 'Cold No Reply', value: 'Cold No Reply' },
            { label: 'Replied', value: 'Replied' },
            { label: 'Warm', value: 'Warm' },
            { label: 'Booked', value: 'Booked' },
            { label: 'Paid', value: 'Paid' },
            { label: 'Tableturnerr Client', value: 'Tableturnerr Client' },
            { label: 'Excluded', value: 'Excluded' },
            { 
                label: isContacted ? 'Mark as Not Contacted' : 'Mark as Contacted Manually', 
                value: isContacted ? 'FLIP_TO_NOT_CONTACTED' : 'FLIP_TO_CONTACTED',
                style: 'color: #ff4444; font-weight: bold;'
            }
        ];
    }

    const optionsHtml = statusOptions.map(opt =>
        `<option value="${opt.value}" ${data.status === opt.value ? 'selected' : ''} style="${opt.style || ''}">${opt.label}</option>`
    ).join('');

    const notesValue = data.notes || '';
    const charLimit = 500;

    switch (state) {
        case 'searching':
            banner.classList.add('insta-warning-banner--searching');
            const searchingIconUrl = chrome.runtime.getURL('assets/searching-icon.svg');
            banner.innerHTML = `<div class="searching-icon-container"><img src="${searchingIconUrl}" /></div><p class="searching-text">Checking...</p>`;
            break;
        case 'offline':
            banner.classList.add('banner-style-base', 'insta-warning-banner--excluded'); // Use charcoal for offline
            banner.innerHTML = `
                <div class="banner-content">
                    <div class="searching-icon-container" style="background-color: #444;"><span style="font-size: 24px;">⚠️</span></div>
                    <div class="contact-details">
                        <p class="contact-title">Application Offline</p>
                        <p class="contact-subtitle">Please ensure the <b>Insta Outreach Logger</b> app is running on your computer.</p>
                        <button id="offline-retry-btn" style="margin-top: 8px; background: #7C3AED; color: white; border: none; border-radius: 4px; padding: 4px 12px; cursor: pointer; font-size: 0.8rem;">Retry Connection</button>
                    </div>
                </div>`;
            banner.querySelector('#offline-retry-btn').onclick = () => runProfileCheck(lastCheckedUsername);
            break;
        case 'contacted':
        case 'not_contacted':
            isDraggable = true;            if (isExcluded) banner.classList.add('banner-style-base', 'insta-warning-banner--excluded');
            else banner.classList.add('banner-style-base', isContacted ? 'insta-warning-banner--contacted' : 'insta-warning-banner--not-contacted');
            
            const iconUrl = chrome.runtime.getURL(isExcluded ? 'assets/contacted-icon.svg' : (isContacted ? 'assets/contacted-icon.svg' : 'assets/not-contacted-icon.svg'));
            const closeIconUrl = chrome.runtime.getURL('assets/close-icon.svg');
            const arrowUrl = chrome.runtime.getURL('assets/dropdown-arrow.svg');
            
            const rawActor = data.owner_actor;
            const actor = (rawActor && rawActor !== 'null' && rawActor !== 'None') ? rawActor : 'Unknown';
            const dateStr = formatDate(data.last_updated);
            
            let subtitle = isExcluded ? `<b style="color:#aaa;">EXCLUDED</b> from logging` :
                          (isContacted ? `By <b style="color:white;">${actor}</b> on <b style="color:white;">${dateStr}</b>` : 'Not Contacted Before');

            banner.innerHTML = `
                <div class="banner-content">
                    <img src="${iconUrl}" class="contact-icon">
                    <div class="contact-details">
                        <div id="banner-step-main">
                            <p class="contact-title">${isExcluded ? 'Excluded Target' : (isContacted ? 'Previously Contacted' : 'Not Contacted Before')}</p>
                            <p class="contact-subtitle">${subtitle}</p>
                            <div class="status-dropdown-wrapper" style="margin-top: 10px;">
                                <select class="status-dropdown">${optionsHtml}</select>
                                <img src="${arrowUrl}" class="dropdown-arrow" />
                            </div>
                            <div class="notes-container" style="margin-top: 10px;">
                                ${notesValue ? 
                                    `<textarea class="notes-textarea" maxlength="${charLimit}">${notesValue}</textarea>
                                     <div class="notes-footer"><span class="char-count">${notesValue.length}/${charLimit}</span><button class="save-notes-btn">Save Note</button></div>` :
                                    `<button class="toggle-notes-btn">Add a Note</button>
                                     <div class="notes-input-wrapper" style="display: none;">
                                        <textarea class="notes-textarea" maxlength="${charLimit}"></textarea>
                                        <div class="notes-footer"><span class="char-count">0/${charLimit}</span><button class="save-notes-btn">Save Note</button></div>
                                     </div>`
                                }
                            </div>
                        </div>
                        <div id="banner-step-manual" style="display: none; width: 280px;">
                            <p class="contact-title">Manual Outreach Entry</p>
                            <div class="manual-form" style="margin-top: 10px; display: flex; flex-direction: column; gap: 8px;">
                                <div class="input-group">
                                    <label style="font-size: 0.75rem; color: #aaa;">Actor Username (Required)</label>
                                    <input type="text" id="manual-actor" list="actor-list" placeholder="Who sent it?" style="width: 100%; background: #000; border: 1px solid #444; color: white; border-radius: 4px; padding: 4px 8px;">
                                    <datalist id="actor-list">${cachedActors.map(a => `<option value="${a}">`).join('')}</datalist>
                                </div>
                                <div class="input-group">
                                    <label style="font-size: 0.75rem; color: #aaa;">Message Snippet</label>
                                    <textarea id="manual-msg" placeholder="What was said?" style="width: 100%; background: #000; border: 1px solid #444; color: white; border-radius: 4px; padding: 4px 8px; height: 40px; resize: none;"></textarea>
                                </div>
                                <div class="input-group">
                                    <label style="font-size: 0.75rem; color: #aaa;">Date & Time (Required)</label>
                                    <input type="datetime-local" id="manual-date" style="width: 100%; background: #000; border: 1px solid #444; color: white; border-radius: 4px; padding: 4px 8px;">
                                </div>
                                <div style="display: flex; gap: 8px; margin-top: 5px;">
                                    <button id="manual-submit" style="flex: 1; background: #7C3AED; color: white; border: none; border-radius: 4px; padding: 6px; cursor: pointer; font-weight: bold;">Save outreach</button>
                                    <button id="manual-cancel" style="background: #333; color: white; border: none; border-radius: 4px; padding: 6px 12px; cursor: pointer;">Cancel</button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <button class="close-btn"><img src="${closeIconUrl}"></button>`;
            break;
        default: return;
    }

    const dropdown = banner.querySelector('.status-dropdown');
    const mainView = banner.querySelector('#banner-step-main');
    const manualView = banner.querySelector('#banner-step-manual');

    if (dropdown) {
        dropdown.addEventListener('change', async () => {
            const val = dropdown.value;
            if (val === 'FLIP_TO_NOT_CONTACTED') {
                if (confirm(`Are you sure you want to mark ${lastCheckedUsername} as NOT CONTACTED?\n\nThis will remove them from the outreach database.`)) {
                    deleteProspect(lastCheckedUsername);
                } else dropdown.value = data.status || '';
            } else if (val === 'FLIP_TO_CONTACTED') {
                mainView.style.display = 'none';
                manualView.style.display = 'block';
                const now = new Date();
                now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
                banner.querySelector('#manual-date').value = now.toISOString().slice(0, 16);
            } else {
                const textarea = banner.querySelector('.notes-textarea');
                updateDropdownSyncStage(dropdown, 'local');
                updateProspectStatus(lastCheckedUsername, val, dropdown, textarea ? textarea.value : null, () => {
                    setTimeout(() => runProfileCheck(lastCheckedUsername, true), 1000);
                });
            }
        });
    }

    if (manualView) {
        banner.querySelector('#manual-cancel').onclick = () => {
            manualView.style.display = 'none'; mainView.style.display = 'block'; dropdown.value = data.status || '';
        };
        banner.querySelector('#manual-submit').onclick = () => {
            const actorInput = banner.querySelector('#manual-actor').value.trim();
            const dateInput = banner.querySelector('#manual-date').value;
            if (!actorInput || !dateInput) { alert("Actor Username and Date are required."); return; }
            if (!cachedActors.includes(actorInput)) {
                if (!confirm(`This account is not registered. Are you sure this is the correct Instagram account "${actorInput}"?`)) return;
            }
            const submitBtn = banner.querySelector('#manual-submit');
            submitBtn.disabled = true; submitBtn.textContent = "Saving...";
            sendMessageToBackground({
                type: 'LOG_OUTREACH',
                payload: { target: lastCheckedUsername, actor: actorInput, message: banner.querySelector('#manual-msg').value.trim() || "[Manual]", timestamp: new Date(dateInput).toISOString() }
            }, (res) => {
                if (res?.success) runProfileCheck(lastCheckedUsername, true);
                else { alert("Error: " + (res?.message || "Unknown")); submitBtn.disabled = false; submitBtn.textContent = "Save outreach"; }
            });
        };
    }

    const toggleNotesBtn = banner.querySelector('.toggle-notes-btn');
    if (toggleNotesBtn) {
        toggleNotesBtn.onclick = (e) => {
            e.stopPropagation();
            const wrapper = banner.querySelector('.notes-input-wrapper');
            if (wrapper) { wrapper.style.display = 'flex'; const ta = wrapper.querySelector('.notes-textarea'); if (ta) setTimeout(() => ta.focus(), 50); toggleNotesBtn.style.display = 'none'; }
        };
    }

    const textarea = banner.querySelector('.notes-textarea');
    if (textarea) {
        textarea.onmousedown = (e) => e.stopPropagation();
        const charCount = banner.querySelector('.char-count');
        textarea.oninput = () => { if (charCount) charCount.textContent = `${textarea.value.length}/${charLimit}`; };
    }

    const saveBtn = banner.querySelector('.save-notes-btn');
    if (saveBtn) {
        saveBtn.onclick = (e) => {
            e.stopPropagation(); saveBtn.textContent = "Saving...";
            updateDropdownSyncStage(dropdown, 'local');
            updateProspectStatus(lastCheckedUsername, dropdown.value, dropdown, textarea.value, () => {
                saveBtn.textContent = "Saved!"; setTimeout(() => saveBtn.textContent = "Save Note", 2000);
            });
        };
    }

    const closeBtn = banner.querySelector('.close-btn');
    if (closeBtn) {
        closeBtn.onclick = (e) => {
            e.stopPropagation();
            banner.classList.add('minimized');
        };
    }

    // Restore banner on click if minimized
    banner.addEventListener('click', (e) => {
        if (banner.classList.contains('minimized')) {
            // Check if we didn't just finish a drag
            banner.classList.remove('minimized');
        }
    });

    const posData = await chrome.storage.local.get('bannerPosition');
    if (isDraggable && posData.bannerPosition?.top) {
        banner.style.top = posData.bannerPosition.top;
        banner.style.left = posData.bannerPosition.left;
    } else { banner.style.top = '20px'; banner.style.right = '20px'; }

    document.body.prepend(banner);
    if (isDraggable) makeDraggable(banner);
    setTimeout(() => banner.classList.add('visible'), 10);
}

function deleteProspect(username) {
    sendMessageToBackground({ type: 'DELETE_PROSPECT', payload: { target: username } }, (res) => {
        if (res?.success) runProfileCheck(username, true);
        else alert("Error: " + (res?.message || "Unknown"));
    });
}

async function updateProspectStatus(username, newStatus, dropdown, notes = null, callback = null) {
    const actorUsername = await getActorUsername();
    
    // Retrieve cached profile data
    chrome.storage.local.get('profileCache', (result) => {
        const cache = result.profileCache || {};
        let profileData = cache[username];

        // Fallback: Scrape immediately if cache is missing
        if (!profileData) {
            console.log(`[InstaLogger] Cache miss for ${username}, scraping on-demand...`);
            profileData = scrapeProfileData(username);
        }

        profileData = profileData || {}; // Ensure object exists

        sendMessageToBackground({
            type: 'UPDATE_PROSPECT_STATUS',
            payload: { 
                target: username, 
                new_status: newStatus, 
                actor: actorUsername, 
                notes: notes,
                profile_data: profileData 
            }
        }, (response) => {
            if (response?.success || response?.data?.success) updateDropdownSyncStage(dropdown, 'synced');
            else updateDropdownSyncStage(dropdown, 'error');
            if (callback) callback();
            setTimeout(() => updateDropdownSyncStage(dropdown, null), 2000);
        });
    });
}

// =============================================================================
// 3. Status Check Logic
// =============================================================================

function getInstagramUsername(inputElement) {
    if (inputElement) {
        let currentElement = inputElement;
        for (let i = 0; i < 25 && currentElement; i++) {
            const links = currentElement.querySelectorAll('a');
            for (const link of links) {
                if (!link.href) continue;
                try {
                    const path = new URL(link.href).pathname;
                    const isNotSpecialRoute = path !== '/' && !path.startsWith('/direct/') && !path.startsWith('/explore/') && !path.startsWith('/reels/') && !path.startsWith('/stories/');
                    if (isNotSpecialRoute) {
                        if ((link.innerText && link.innerText.toLowerCase().includes('view profile')) || /^\/[a-zA-Z0-9_.]+\/?$/.test(path)) {
                            const username = path.split('/').filter(p => p)[0];
                            if (username) return username;
                        }
                    }
                } catch (e) {}
            }
            currentElement = currentElement.parentElement;
        }
    }
    const mainContent = document.querySelector('div[role="main"]');
    if (mainContent) {
        const headerLinks = mainContent.querySelectorAll('header a[href^="/"]');
        for (const link of headerLinks) {
             const href = link.getAttribute('href');
             const match = href.match(/^\/([a-zA-Z0-9_.]+)\/?$/);
             if (match && match[1] && !['explore', 'direct', 'reels', 'stories'].includes(match[1])) return match[1];
        }
        const headerTitle = mainContent.querySelector('h2');
        if (headerTitle) {
            const parentLink = headerTitle.closest('a');
            if (parentLink) {
                 const href = parentLink.getAttribute('href');
                 const match = href.match(/^\/([a-zA-Z0-9_.]+)\/?$/);
                 if (match && match[1]) return match[1];
            }
        }
    }
    const pathParts = window.location.pathname.split('/').filter(p => p);
    if (pathParts.length === 1 && !['explore', 'reels', 'inbox', 'direct', 'accounts', 'login'].includes(pathParts[0])) return pathParts[0];
    return pathParts.includes('t') ? "unknown_user_in_thread" : "not_in_a_dm_thread";
}

async function runProfileCheck(username, silentRefresh = false) {
    if (isCheckInProgress) return;
    isCheckInProgress = true;
    const checkStartedForUsername = username;
    lastCheckedUsername = username;
    if (!silentRefresh) await showStatusBanner('searching', { syncStage: 'local' });
    sendMessageToBackground({ type: 'CHECK_PROSPECT_STATUS', payload: { target: username } }, async (response) => {
        if (lastCheckedUsername !== checkStartedForUsername) { isCheckInProgress = false; return; }
        
        if (response?.message === 'APPLICATION_OFFLINE') {
            await showStatusBanner('offline');
            isCheckInProgress = false;
            return;
        }

        if (response?.error || response?.success === false) {
            updateSyncStage(document.getElementById('insta-warning-banner'), 'error');
            isCheckInProgress = false;
            return;
        }
        const data = response?.data || response;
        if (data?.contacted) await showStatusBanner('contacted', { status: data.status, owner_actor: data.owner_actor, last_updated: data.last_updated, notes: data.notes, syncStage: 'complete' });
        else await showStatusBanner('not_contacted', { syncStage: 'not-found' });
        isCheckInProgress = false;
    });
}

function handleVisibilityChange() {
    if (document.visibilityState === 'visible' && lastCheckedUsername && !isCheckInProgress) runProfileCheck(lastCheckedUsername, true);
}
document.addEventListener('visibilitychange', handleVisibilityChange);

// =============================================================================
// 4. DM Logging
// =============================================================================

async function getActorUsername() {
    try {
        const result = await chrome.storage.local.get('actorUsername');
        return result.actorUsername || 'unknown_actor';
    } catch (e) { return 'unknown_actor'; }
}

async function logOutreach(inputElement) {
    const text = (inputElement.textContent || inputElement.innerText).trim();
    if (!text) return;
    const actor = await getActorUsername();
    if (!lastCheckedUsername || lastCheckedUsername.startsWith('unknown') || actor === 'unknown_actor') return;
    
    // Retrieve cached profile data to send with the log
    chrome.storage.local.get('profileCache', (result) => {
        const cache = result.profileCache || {};
        let profileData = cache[lastCheckedUsername];
        
        // Fallback: Scrape immediately if cache is missing
        if (!profileData) {
            console.log(`[InstaLogger] Cache miss for ${lastCheckedUsername}, scraping on-demand...`);
            profileData = scrapeProfileData(lastCheckedUsername);
        }

        profileData = profileData || {};

        sendMessageToBackground({ 
            type: 'LOG_OUTREACH', 
            payload: { 
                target: lastCheckedUsername, 
                actor: actor, 
                message: text.substring(0, 200),
                profile_data: profileData 
            } 
        }, (res) => {
            if (res?.success || res?.data?.log_id) setTimeout(() => { if (lastCheckedUsername && !isCheckInProgress) runProfileCheck(lastCheckedUsername, true); }, 500);
        });
    });
}

function handleKeyDown(e) { if (e.key === 'Enter' && !e.shiftKey) logOutreach(e.target); }

function findAndAttach() {
    if (!window.location.pathname.startsWith('/direct/')) return;
    const chatInput = document.querySelector(CHAT_INPUT_SELECTOR);
    if (chatInput && chatInput !== activeChatInput) {
        if (activeChatInput) activeChatInput.removeEventListener('keydown', handleKeyDown, { capture: true });
        chatInput.addEventListener('keydown', handleKeyDown, { capture: true });
        activeChatInput = chatInput;
    }
}

// =============================================================================
// 5. URL Router
// =============================================================================

let dmDiscoveryInterval = null;
const handleUrlChange = () => {
    const url = window.location.href;
    if (url === lastCheckedUrl) return;
    lastCheckedUrl = url;
    if (isCheckInProgress) isCheckInProgress = false;
    if (dmDiscoveryInterval) { clearInterval(dmDiscoveryInterval); dmDiscoveryInterval = null; }
    document.querySelectorAll('.insta-warning-banner').forEach(b => b.remove());
    stopBannerPulse();
    const profileMatch = url.match(/https:\/\/www\.instagram\.com\/([a-zA-Z0-9_.]+)/);
    if (profileMatch && profileMatch[1] && !['explore', 'reels', 'inbox', 'direct', 'accounts', 'login', 'p'].includes(profileMatch[1])) {
        lastCheckedUsername = profileMatch[1]; 
        runProfileCheck(profileMatch[1]);
        // Trigger scraping
        setTimeout(() => cacheProfile(profileMatch[1]), 1500);
    } else if (url.includes('/direct/t/')) {
        showStatusBanner('searching', { syncStage: 'local' });
        let attempts = 0;
        dmDiscoveryInterval = setInterval(() => {
            attempts++;
            if (window.location.href !== url) { clearInterval(dmDiscoveryInterval); return; }
            const dmUser = getInstagramUsername(document.querySelector(CHAT_INPUT_SELECTOR) || document.querySelector('div[role="main"]'));
            if (dmUser && !dmUser.startsWith('unknown')) { clearInterval(dmDiscoveryInterval); dmDiscoveryInterval = null; lastCheckedUsername = dmUser; runProfileCheck(dmUser); }
            else if (attempts >= 20) { clearInterval(dmDiscoveryInterval); updateSyncStage(document.getElementById('insta-warning-banner'), 'detection-failed'); }
        }, 500);
    }
};

function initialize() {
    connectPort();
    fetchCachedActors();
    startActorVerification();
    const observer = new MutationObserver(() => setTimeout(handleUrlChange, 50));
    observer.observe(document.body, { childList: true, subtree: true });
    setInterval(findAndAttach, 1000);
    setTimeout(handleUrlChange, 300);
}

initialize();
