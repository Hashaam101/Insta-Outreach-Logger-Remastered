/**
 * Insta Outreach Logger - Content Script (v12 - Hardened Auto-Discovery)
 *
 * This script has three modes:
 * 1. Discovery Mode: If on instagram.com homepage with discover_actor param,
 *    it finds the user's profile link and sends the username to the background script.
 * 2. Profile/DM Check Mode: On profile pages or DM threads, it checks the prospect
 *    status via IPC and shows a status banner.
 * 3. Logging Mode: On DM pages, it captures sent messages and logs them.
 *
 * v12 Enhancements:
 * - MutationObserver for SPA navigation detection
 * - Periodic actor username verification (detects account switching)
 * - Auto-refresh banner when actor changes
 */

console.log('[InstaLogger] Content Script Loaded (v12 - Hardened Auto-Discovery)');

// =============================================================================
// Globals & State
// =============================================================================
const CHAT_INPUT_SELECTOR = 'div[role="textbox"][aria-label="Message"]';
const ACTOR_CHECK_INTERVAL = 5000; // Check for account switches every 5 seconds

let activeChatInput = null;
let lastCheckedUrl = '';
let lastCheckedUsername = '';
let isCheckInProgress = false;
let bannerPulseInterval = null;
let actorCheckInterval = null;
let currentActorUsername = null; // Cached actor username for switch detection

// Port connection to background script
let port = null;
let pendingCallbacks = new Map();
let messageIdCounter = 0;

function connectPort() {
    try {
        port = chrome.runtime.connect({ name: 'content-script' });

        port.onMessage.addListener((message) => {
            // Handle PUSH notifications from backend (Push-based Sync)
            if (message.type === 'SYNC_COMPLETED') {
                console.log('[InstaLogger] Received SYNC_COMPLETED event from backend.');
                // Only refresh if we are currently looking at a profile
                if (lastCheckedUsername && document.visibilityState === 'visible') {
                    console.log(`[InstaLogger] Triggering refresh for ${lastCheckedUsername} due to sync.`);
                    runProfileCheck(lastCheckedUsername, true); // silent refresh
                }
                return;
            }

            // Handle responses from IPC server
            if (message.requestId && pendingCallbacks.has(message.requestId)) {
                const callback = pendingCallbacks.get(message.requestId);
                pendingCallbacks.delete(message.requestId);
                callback(message);
            }
        });

        port.onDisconnect.addListener(() => {
            console.log('[InstaLogger] Port disconnected, reconnecting...');
            port = null;
            setTimeout(connectPort, 1000);
        });
    } catch (e) {
        console.error('[InstaLogger] Failed to connect port:', e);
    }
}

function sendMessageToBackground(data, callback) {
    if (!port) {
        connectPort();
    }

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
// 1. Discovery Mode Logic
// =============================================================================
function runDiscovery() {
    console.log('[InstaLogger] Running in Discovery Mode...');
    let attempts = 0;
    const maxAttempts = 50;

    const discoveryInterval = setInterval(() => {
        attempts++;
        const profileLink = Array.from(document.querySelectorAll('a'))
            .find(a => a.href && a.querySelector('img') && a.href.endsWith(`/${a.innerText.toLowerCase()}/`));

        let profileLinkByText = null;
        if (!profileLink) {
            profileLinkByText = Array.from(document.querySelectorAll('a'))
                .find(a => a.textContent.trim() === 'Profile');
        }

        const finalProfileLink = profileLink || profileLinkByText;

        if (finalProfileLink && finalProfileLink.href) {
            clearInterval(discoveryInterval);
            const href = finalProfileLink.getAttribute('href');
            const match = href.match(/^\/([a-zA-Z0-9_.]+)\//);
            if (match && match[1]) {
                const username = match[1];
                console.log(`[InstaLogger] Discovery SUCCESS: Found username "${username}".`);
                sendMessageToBackground({ type: 'FOUND_ACTOR_USERNAME', username: username });
            }
        } else if (attempts > maxAttempts) {
            clearInterval(discoveryInterval);
            console.error('[InstaLogger] Discovery FAILED: Could not find profile link after 5 seconds.');
        }
    }, 100);
}

// =============================================================================
// 1b. Hardened Actor Discovery (SPA Account Switch Detection)
// =============================================================================

function scrapeCurrentViewerUsername() {
    const profileLinks = Array.from(document.querySelectorAll('a[href^="/"]'));

    for (const link of profileLinks) {
        const href = link.getAttribute('href');
        if (!href) continue;

        const hasProfileImg = link.querySelector('img[alt*="profile" i]') ||
                             link.querySelector('img[data-testid="user-avatar"]');

        if (hasProfileImg) {
            const match = href.match(/^\/([a-zA-Z0-9_.]+)\/?$/);
            if (match && match[1] && !['explore', 'reels', 'inbox', 'direct', 'accounts', 'p'].includes(match[1])) {
                return match[1];
            }
        }

        if (link.textContent.trim().toLowerCase() === 'profile') {
            const match = href.match(/^\/([a-zA-Z0-9_.]+)\/?$/);
            if (match && match[1]) {
                return match[1];
            }
        }
    }

    const moreMenuLinks = document.querySelectorAll('a[href*="/accounts/"]');
    for (const link of moreMenuLinks) {
        const parent = link.closest('div[role="dialog"]') || link.closest('nav');
        if (parent) {
            const profileLink = parent.querySelector('a[href^="/"]:not([href*="/accounts/"])');
            if (profileLink) {
                const href = profileLink.getAttribute('href');
                const match = href.match(/^\/([a-zA-Z0-9_.]+)\/?$/);
                if (match && match[1] && !['explore', 'reels', 'inbox', 'direct'].includes(match[1])) {
                    return match[1];
                }
            }
        }
    }

    return null;
}

async function handleActorSwitch(newUsername) {
    console.log(`[InstaLogger][Actor] Account switch detected: ${currentActorUsername} -> ${newUsername}`);
    currentActorUsername = newUsername;
    await chrome.storage.local.set({ actorUsername: newUsername });

    sendMessageToBackground({
        type: 'ACTOR_SWITCH',
        payload: { old_actor: currentActorUsername, new_actor: newUsername }
    });

    if (lastCheckedUsername && !isCheckInProgress) {
        runProfileCheck(lastCheckedUsername, true);
    }
}

async function checkForActorSwitch() {
    let storedUsername;
    try {
        const stored = await chrome.storage.local.get('actorUsername');
        storedUsername = stored.actorUsername;
    } catch (e) {
        if (e.message.includes('Extension context invalidated')) {
            console.log('[InstaLogger] Extension context invalidated. Stopping actor checks.');
            if (actorCheckInterval) clearInterval(actorCheckInterval);
            return;
        }
        console.error('[InstaLogger] Error checking actor username:', e);
        return;
    }

    const scrapedUsername = scrapeCurrentViewerUsername();

    // If we can't scrape the username AND we don't have one stored, we are lost.
    if (!scrapedUsername) {
        if (!storedUsername) {
            // We don't know who the user is, and we can't see it on the page.
            // Request the background script to help us find it.
            sendMessageToBackground({ type: 'REQUEST_ACTOR_DISCOVERY' });
        }
        return;
    }

    if (!currentActorUsername && storedUsername) {
        currentActorUsername = storedUsername;
    }

    if (storedUsername && scrapedUsername !== storedUsername) {
        await handleActorSwitch(scrapedUsername);
    } else if (!storedUsername && scrapedUsername) {
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
// 2. UI Banner System
// =============================================================================

function makeDraggable(element) {
    let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;

    function dragMouseDown(e) {
        if (e.target.closest('.close-btn') || e.target.closest('.status-dropdown-wrapper') || e.target.closest('.notes-container')) {
            return;
        }
        e.preventDefault();
        pos3 = e.clientX;
        pos4 = e.clientY;
        document.body.classList.add('insta-logger-dragging');
        document.addEventListener('mouseup', closeDragElement);
        document.addEventListener('mousemove', elementDrag);
    }

    function elementDrag(e) {
        e.preventDefault();
        pos1 = pos3 - e.clientX;
        pos2 = pos4 - e.clientY;
        pos3 = e.clientX;
        pos4 = e.clientY;
        let newTop = element.offsetTop - pos2;
        let newLeft = element.offsetLeft - pos1;
        const winWidth = window.innerWidth;
        const winHeight = window.innerHeight;
        const elmWidth = element.offsetWidth;
        const elmHeight = element.offsetHeight;
        newLeft = Math.max(0, Math.min(newLeft, winWidth - elmWidth));
        newTop = Math.max(0, Math.min(newTop, winHeight - elmHeight));
        element.style.top = newTop + "px";
        element.style.left = newLeft + "px";
        element.style.right = '';
        element.style.transform = '';
    }

    function closeDragElement() {
        document.body.classList.remove('insta-logger-dragging');
        document.removeEventListener('mouseup', closeDragElement);
        document.removeEventListener('mousemove', elementDrag);
        const finalPosition = { top: element.style.top, left: element.style.left };
        chrome.storage.local.set({ bannerPosition: finalPosition });
    }

    function handleClick(e) {
        if (e.target.closest('.close-btn')) {
            element.classList.add('minimized');
        } else if (element.classList.contains('minimized')) {
            const dx = Math.abs(e.clientX - pos3);
            const dy = Math.abs(e.clientY - pos4);
            if (dx < 5 && dy < 5) {
                element.classList.remove('minimized');
            }
        }
    }

    element.addEventListener('mousedown', dragMouseDown);
    element.addEventListener('click', handleClick);

    return {
        destroy: () => {
            element.removeEventListener('mousedown', dragMouseDown);
            element.removeEventListener('click', handleClick);
        }
    };
}

function startBannerPulse(banner, r, g, b) {
    if (bannerPulseInterval) clearInterval(bannerPulseInterval);
    let isPulsed = false;
    bannerPulseInterval = setInterval(() => {
        if (!banner || !document.body.contains(banner)) {
            clearInterval(bannerPulseInterval);
            return;
        }
        if (isPulsed) {
            banner.style.boxShadow = `0 0 8px rgba(${r}, ${g}, ${b}, 0.4)`;
        } else {
            banner.style.boxShadow = `0 0 25px rgba(${r}, ${g}, ${b}, 1.0)`;
        }
        isPulsed = !isPulsed;
    }, 600);
}

function stopBannerPulse() {
    if (bannerPulseInterval) {
        clearInterval(bannerPulseInterval);
        bannerPulseInterval = null;
    }
}

function updateSyncStage(banner, stage) {
    if (!banner) return;
    stopBannerPulse();
    banner.style.boxShadow = '';
    const allStages = ['sync-stage-local', 'sync-stage-cloud', 'sync-stage-downloading', 'sync-stage-complete', 'sync-stage-not-found', 'sync-stage-error', 'sync-stage-detection-failed'];
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
    } catch (e) {
        return 'Unknown Date';
    }
}

async function showStatusBanner(state, data = {}) {
    document.querySelectorAll('.insta-warning-banner').forEach(b => b.remove());

    const banner = document.createElement('div');
    banner.id = 'insta-warning-banner';
    banner.className = 'insta-warning-banner';
    banner.dataset.state = state;

    if (data.syncStage) {
        banner.classList.add(`sync-stage-${data.syncStage}`);
        if(data.syncStage === 'detection-failed') startBannerPulse(banner, 255, 69, 0);
    }

    let isDraggable = false;
    const STATUS_OPTIONS = ['Cold_NoReply', 'Rejected', 'Warm', 'Hot', 'Booked', 'Client'];
    const optionsHtml = STATUS_OPTIONS.map(option =>
        `<option value="${option}" ${data.status === option ? 'selected' : ''}>${option.replace('_', ' ')}</option>`
    ).join('');

    const notesValue = data.notes || '';
    const charLimit = 500;

    switch (state) {
        case 'searching':
            banner.classList.add('insta-warning-banner--searching');
            const searchingIconUrl = chrome.runtime.getURL('assets/searching-icon.svg');
            banner.innerHTML = `<div class="searching-icon-container"><img src="${searchingIconUrl}" /></div><p class="searching-text">Checking...</p>`;
            break;
        case 'contacted':
        case 'not_contacted':
            isDraggable = true;
            const isContacted = state === 'contacted';
            banner.classList.add('banner-style-base', isContacted ? 'insta-warning-banner--contacted' : 'insta-warning-banner--not-contacted');
            
            const iconUrl = chrome.runtime.getURL(isContacted ? 'assets/contacted-icon.svg' : 'assets/not-contacted-icon.svg');
            const closeIconUrl = chrome.runtime.getURL('assets/close-icon.svg');
            const arrowUrl = chrome.runtime.getURL('assets/dropdown-arrow.svg');
            
            const rawActor = data.owner_actor;
            const actor = (rawActor && rawActor !== 'null' && rawActor !== 'None') ? rawActor : 'Unknown';
            const dateStr = formatDate(data.last_updated);
            const subtitle = isContacted ? `By <b style="color:white;">${actor}</b> on <b style="color:white;">${dateStr}</b>` : 'Not Contacted Before';
            const hasNotes = notesValue && notesValue.trim().length > 0;

            banner.innerHTML = `
                <div class="banner-content">
                    <img src="${iconUrl}" class="contact-icon">
                    <div class="contact-details">
                        <p class="contact-title">${isContacted ? 'Previously Contacted' : 'Not Contacted Before'}</p>
                        <p class="contact-subtitle">${subtitle}</p>
                        <div class="status-dropdown-wrapper">
                            <select class="status-dropdown">${optionsHtml}</select>
                            <img src="${arrowUrl}" class="dropdown-arrow" />
                        </div>
                        <div class="notes-container">
                            ${hasNotes ? 
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
                </div>
                <button class="close-btn"><img src="${closeIconUrl}"></button>`;
            break;
        default: return;
    }

    const dropdown = banner.querySelector('.status-dropdown');
    if (dropdown) {
        dropdown.addEventListener('change', () => {
            const textarea = banner.querySelector('.notes-textarea');
            updateDropdownSyncStage(dropdown, 'local');
            updateProspectStatus(lastCheckedUsername, dropdown.value, dropdown, textarea ? textarea.value : null);
        });
    }

    const toggleNotesBtn = banner.querySelector('.toggle-notes-btn');
    if (toggleNotesBtn) {
        toggleNotesBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const wrapper = banner.querySelector('.notes-input-wrapper');
            if (wrapper) {
                wrapper.style.display = 'flex';
                const textarea = wrapper.querySelector('.notes-textarea');
                if (textarea) setTimeout(() => textarea.focus(), 50);
                toggleNotesBtn.style.display = 'none';
            }
        });
    }

    const textarea = banner.querySelector('.notes-textarea');
    if (textarea) {
        textarea.addEventListener('mousedown', (e) => e.stopPropagation());
        const charCount = banner.querySelector('.char-count');
        textarea.addEventListener('input', () => { if (charCount) charCount.textContent = `${textarea.value.length}/${charLimit}`; });
    }

    const saveBtn = banner.querySelector('.save-notes-btn');
    if (saveBtn) {
        saveBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            saveBtn.textContent = "Saving...";
            updateDropdownSyncStage(dropdown, 'local');
            updateProspectStatus(lastCheckedUsername, dropdown.value, dropdown, textarea.value, () => {
                saveBtn.textContent = "Saved!";
                setTimeout(() => saveBtn.textContent = "Save Note", 2000);
            });
        });
    }

    const posData = await chrome.storage.local.get('bannerPosition');
    if (isDraggable && posData.bannerPosition?.top) {
        banner.style.top = posData.bannerPosition.top;
        banner.style.left = posData.bannerPosition.left;
    } else {
        banner.style.top = '20px';
        banner.style.right = '20px';
    }

    document.body.prepend(banner);
    if (isDraggable) makeDraggable(banner);
    setTimeout(() => banner.classList.add('visible'), 10);
}

async function updateProspectStatus(username, newStatus, dropdown, notes = null, callback = null) {
    const actorUsername = await getActorUsername();
    sendMessageToBackground({
        type: 'UPDATE_PROSPECT_STATUS',
        payload: { target: username, new_status: newStatus, actor: actorUsername, notes: notes }
    }, (response) => {
        const data = response?.data || response;
        if (response?.success || data?.success) {
            updateDropdownSyncStage(dropdown, 'synced');
            if (callback) callback();
        } else {
            updateDropdownSyncStage(dropdown, 'error');
            if (callback) callback();
        }
        setTimeout(() => updateDropdownSyncStage(dropdown, null), 2000);
    });
}

// =============================================================================
// 3. Profile Status Check Logic
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

function handleVisibilityChange() {
    if (document.visibilityState === 'visible' && lastCheckedUsername && !isCheckInProgress) {
        runProfileCheck(lastCheckedUsername, true);
    }
}
document.addEventListener('visibilitychange', handleVisibilityChange);

async function runProfileCheck(username, silentRefresh = false) {
    if (isCheckInProgress) return;
    isCheckInProgress = true;
    const checkStartedForUsername = username;
    lastCheckedUsername = username;

    if (!silentRefresh) await showStatusBanner('searching', { syncStage: 'local' });

    sendMessageToBackground({ type: 'CHECK_PROSPECT_STATUS', payload: { target: username } }, async (response) => {
        if (lastCheckedUsername !== checkStartedForUsername) {
            isCheckInProgress = false;
            return;
        }
        if (response?.error || response?.success === false) {
            updateSyncStage(document.getElementById('insta-warning-banner'), 'error');
            isCheckInProgress = false;
            return;
        }

        const data = response?.data || response;
        if (data?.contacted) {
            await showStatusBanner('contacted', { status: data.status, owner_actor: data.owner_actor, last_updated: data.last_updated, notes: data.notes, syncStage: 'complete' });
        } else {
            await showStatusBanner('not_contacted', { syncStage: 'not-found' });
        }
        isCheckInProgress = false;
    });
}

function waitForElement(selector, callback, timeout = 5000) {
    const startTime = Date.now();
    const timer = setInterval(() => {
        const element = document.querySelector(selector);
        if (element) { clearInterval(timer); callback(element); }
        else if (Date.now() - startTime > timeout) clearInterval(timer);
    }, 200);
}

// =============================================================================
// 4. DM Logging Mode Logic
// =============================================================================

async function getActorUsername() {
    try {
        const result = await chrome.storage.local.get('actorUsername');
        return result.actorUsername || 'unknown_actor';
    } catch (e) { return 'unknown_actor'; }
}

async function logOutreach(inputElement) {
    const messageText = inputElement.textContent || inputElement.innerText;
    if (!messageText || !messageText.trim()) return;

    const actorUsername = await getActorUsername();
    let targetUsername = lastCheckedUsername; // Use the globally tracked username

    if (!targetUsername || targetUsername === 'unknown_target' || actorUsername === 'unknown_actor') return;

    sendMessageToBackground({
        type: 'LOG_OUTREACH',
        payload: { target: targetUsername, actor: actorUsername, message: messageText.trim().substring(0, 200) }
    }, (response) => {
        if (response?.success || response?.data?.log_id) {
            setTimeout(() => { if (lastCheckedUsername && !isCheckInProgress) runProfileCheck(lastCheckedUsername, true); }, 500);
        }
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
// 5. URL Change Handler (Main Router)
// =============================================================================

let dmDiscoveryInterval = null;

const handleUrlChange = () => {
    const currentUrl = window.location.href;
    if (currentUrl === lastCheckedUrl) return;
    lastCheckedUrl = currentUrl;
    if (isCheckInProgress) isCheckInProgress = false;

    if (dmDiscoveryInterval) { clearInterval(dmDiscoveryInterval); dmDiscoveryInterval = null; }
    document.querySelectorAll('.insta-warning-banner').forEach(b => b.remove());
    stopBannerPulse();

    const profileMatch = currentUrl.match(/https:\/\/www\.instagram\.com\/([a-zA-Z0-9_.]+)\/?$/);
    const directRegex = /https:\/\/www\.instagram\.com\/direct\/t\//;

    if (profileMatch && profileMatch[1] && !['explore', 'reels', 'inbox', 'direct', 'accounts', 'login', 'p'].includes(profileMatch[1])) {
        lastCheckedUsername = profileMatch[1];
        runProfileCheck(profileMatch[1]);
    } 
    else if (directRegex.test(currentUrl)) {
        showStatusBanner('searching', { syncStage: 'local' });
        let attempts = 0;
        dmDiscoveryInterval = setInterval(() => {
            attempts++;
            if (window.location.href !== currentUrl) { clearInterval(dmDiscoveryInterval); return; }
            const chatContainer = document.querySelector('div[role="main"]');
            const chatInput = document.querySelector(CHAT_INPUT_SELECTOR);
            const dmUsername = getInstagramUsername(chatInput || chatContainer);
            
            if (dmUsername && dmUsername !== "unknown_user_in_thread" && dmUsername !== "not_in_a_dm_thread") {
                clearInterval(dmDiscoveryInterval);
                dmDiscoveryInterval = null;
                lastCheckedUsername = dmUsername;
                runProfileCheck(dmUsername);
            } else if (attempts >= 20) {
                clearInterval(dmDiscoveryInterval);
                updateSyncStage(document.getElementById('insta-warning-banner'), 'detection-failed');
            }
        }, 500);
    }
};

// =============================================================================
// Initialization
// =============================================================================
function initialize() {
    connectPort();
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('discover_actor') === 'true') { runDiscovery(); return; }

    startActorVerification();
    const observer = new MutationObserver(() => setTimeout(handleUrlChange, 50));
    observer.observe(document.body, { childList: true, subtree: true });

    setInterval(findAndAttach, 1000);

    setTimeout(() => {
        const currentUrl = window.location.href;
        const profileMatch = currentUrl.match(/https:\/\/www\.instagram\.com\/([a-zA-Z0-9_.]+)\/?$/);
        const directRegex = /https:\/\/www\.instagram\.com\/direct\/t\//;

        if (profileMatch && profileMatch[1] && !['explore', 'reels', 'inbox', 'direct', 'accounts', 'login', 'p'].includes(profileMatch[1])) {
            lastCheckedUrl = currentUrl;
            lastCheckedUsername = profileMatch[1];
            runProfileCheck(profileMatch[1]);
        } else if (directRegex.test(currentUrl)) {
            lastCheckedUrl = currentUrl;
            showStatusBanner('searching', { syncStage: 'local' });
            waitForElement('div[role="main"]', (element) => {
                const chatInput = document.querySelector(CHAT_INPUT_SELECTOR);
                const dmUsername = getInstagramUsername(chatInput || element);
                if (dmUsername && dmUsername !== "unknown_user_in_thread" && dmUsername !== "not_in_a_dm_thread") {
                    lastCheckedUsername = dmUsername;
                    runProfileCheck(dmUsername);
                } else {
                     updateSyncStage(document.getElementById('insta-warning-banner'), 'detection-failed');
                }
            });
        }
    }, 300);
}

initialize();