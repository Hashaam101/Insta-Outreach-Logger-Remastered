/**
 * Insta Outreach Logger - Content Script (v11 - Real-Time Status Check)
 *
 * This script has three modes:
 * 1. Discovery Mode: If on instagram.com homepage with discover_actor param,
 *    it finds the user's profile link and sends the username to the background script.
 * 2. Profile/DM Check Mode: On profile pages or DM threads, it checks the prospect
 *    status via IPC and shows a status banner.
 * 3. Logging Mode: On DM pages, it captures sent messages and logs them.
 */

console.log('[InstaLogger] Content Script Loaded (v11 - Real-Time Status Check)');

// =============================================================================
// Globals & State
// =============================================================================
const CHAT_INPUT_SELECTOR = 'div[role="textbox"][aria-label="Message"]';
const STATUS_REFRESH_INTERVAL = 30000; // Refresh status every 30 seconds

let activeChatInput = null;
let lastCheckedUrl = '';
let lastCheckedUsername = '';
let isCheckInProgress = false;
let bannerPulseInterval = null;
let statusRefreshInterval = null;

// Port connection to background script
let port = null;
let pendingCallbacks = new Map();
let messageIdCounter = 0;

function connectPort() {
    try {
        port = chrome.runtime.connect({ name: 'content-script' });

        port.onMessage.addListener((message) => {
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
// 2. UI Banner System
// =============================================================================

function makeDraggable(element) {
    let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;

    function dragMouseDown(e) {
        if (e.target.closest('.close-btn') || e.target.closest('.status-dropdown-wrapper')) {
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

    const allStages = ['sync-stage-local', 'sync-stage-cloud', 'sync-stage-downloading', 'sync-stage-complete', 'sync-stage-not-found', 'sync-stage-error'];
    banner.classList.remove(...allStages);

    if (stage) {
        banner.classList.add(`sync-stage-${stage}`);
        console.log(`[InstaLogger][UI] Sync stage updated: ${stage}`);

        if (stage === 'local') startBannerPulse(banner, 245, 158, 11);
        else if (stage === 'downloading') startBannerPulse(banner, 16, 185, 129);
        else if (stage === 'error') startBannerPulse(banner, 239, 68, 68);
    }
}

function updateDropdownSyncStage(dropdown, stage) {
    if (!dropdown) return;
    dropdown.classList.remove(
        'status-sync-local',
        'status-sync-queued',
        'status-sync-synced',
        'status-sync-error'
    );
    if (stage) {
        dropdown.classList.add(`status-sync-${stage}`);
        console.log(`[InstaLogger][UI] Dropdown sync stage: ${stage}`);
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
    }

    let isDraggable = false;

    const STATUS_OPTIONS = ['Cold_NoReply', 'Rejected', 'Warm', 'Hot', 'Booked', 'Client'];
    const optionsHtml = STATUS_OPTIONS.map(option =>
        `<option value="${option}" ${data.status === option ? 'selected' : ''}>${option.replace('_', ' ')}</option>`
    ).join('');

    switch (state) {
        case 'searching':
            banner.classList.add('insta-warning-banner--searching');
            const searchingIconUrl = chrome.runtime.getURL('assets/searching-icon.svg');
            banner.innerHTML = `
                <div class="searching-icon-container">
                    <img src="${searchingIconUrl}" alt="Searching..." />
                </div>
                <p class="searching-text">Checking...</p>
            `;
            break;
        case 'contacted':
            isDraggable = true;
            banner.classList.add('banner-style-base', `insta-warning-banner--contacted`);
            const contactedIconUrl = chrome.runtime.getURL(`assets/contacted-icon.svg`);
            const contactedCloseIconUrl = chrome.runtime.getURL('assets/close-icon.svg');
            const contactedDropdownArrowUrl = chrome.runtime.getURL('assets/dropdown-arrow.svg');
            banner.innerHTML = `
                <div class="banner-content">
                    <img src="${contactedIconUrl}" alt="Previously contacted" class="contact-icon">
                    <div class="contact-details">
                        <p class="contact-title">Previously Contacted</p>
                        <div class="status-dropdown-wrapper"><select class="status-dropdown">${optionsHtml}</select><img src="${contactedDropdownArrowUrl}" class="dropdown-arrow" /></div>
                    </div>
                </div>
                <button class="close-btn"><img src="${contactedCloseIconUrl}" alt="Minimize"></button>
            `;
            break;
        case 'not_contacted':
            isDraggable = true;
            banner.classList.add('banner-style-base', `insta-warning-banner--not-contacted`);
            const notContactedIconUrl = chrome.runtime.getURL('assets/not-contacted-icon.svg');
            const notContactedCloseIconUrl = chrome.runtime.getURL('assets/close-icon.svg');
            const notContactedDropdownArrowUrl = chrome.runtime.getURL('assets/dropdown-arrow.svg');
            banner.innerHTML = `
                <div class="banner-content">
                    <img src="${notContactedIconUrl}" alt="Not Contacted Before" class="contact-icon">
                    <div class="contact-details">
                        <p class="contact-title">Not Contacted Before</p>
                        <div class="status-dropdown-wrapper"><select class="status-dropdown">${optionsHtml}</select><img src="${notContactedDropdownArrowUrl}" class="dropdown-arrow" /></div>
                    </div>
                </div>
                <button class="close-btn"><img src="${notContactedCloseIconUrl}" alt="Minimize"></button>
            `;
            break;
        default: return;
    }

    const dropdown = banner.querySelector('.status-dropdown');
    if (dropdown) {
        dropdown.addEventListener('change', () => {
            const newStatus = dropdown.value;
            const username = lastCheckedUsername;
            if (username && username !== "not_in_a_dm_thread" && username !== "unknown_target") {
                updateDropdownSyncStage(dropdown, 'local');
                updateProspectStatus(username, newStatus, dropdown);
            }
        });
    }

    const posData = await chrome.storage.local.get('bannerPosition');
    if (isDraggable && posData.bannerPosition?.top && posData.bannerPosition?.left) {
        banner.style.top = posData.bannerPosition.top;
        banner.style.left = posData.bannerPosition.left;
    } else {
        banner.style.top = '20px';
        banner.style.right = '20px';
    }

    document.body.prepend(banner);
    if (isDraggable) makeDraggable(banner);

    setTimeout(() => banner.classList.add('visible'), 10);

    if (state === 'searching') {
        setTimeout(() => {
            banner.classList.remove('visible');
            setTimeout(() => banner.remove(), 500);
        }, 3000);
    }
}

async function updateProspectStatus(username, newStatus, dropdown) {
    // Get actor username for logging the status change event
    const actorUsername = await getActorUsername();

    sendMessageToBackground({
        type: 'UPDATE_PROSPECT_STATUS',
        payload: { target: username, new_status: newStatus, actor: actorUsername }
    }, (response) => {
        // Response data is nested under 'data' key from create_ack_response
        const data = response?.data || response;

        if (response?.success || data?.success) {
            updateDropdownSyncStage(dropdown, 'synced');
            console.log(`[InstaLogger][UI] Status updated for ${username}: ${newStatus}`);

            // Update the banner to show "contacted" state with new status
            // (in case it was "not_contacted" before)
            setTimeout(async () => {
                await showStatusBanner('contacted', { status: newStatus, syncStage: 'complete' });
                startStatusRefresh(username);
            }, 1500);
        } else {
            updateDropdownSyncStage(dropdown, 'error');
            console.error(`[InstaLogger][UI] Failed to update status for ${username}`);
        }

        setTimeout(() => {
            updateDropdownSyncStage(dropdown, null);
        }, 2000);
    });
}

// =============================================================================
// 3. Profile Status Check Logic
// =============================================================================

function getInstagramUsername(inputElement) {
    console.log("[InstaLogger] Running Proximity Climber strategy...");
    let currentElement = inputElement;
    for (let i = 0; i < 25 && currentElement; i++) {
        const links = currentElement.querySelectorAll('a');
        for (const link of links) {
            if (!link.href) continue;
            try {
                const path = new URL(link.href).pathname;
                const isNotSpecialRoute = path !== '/' &&
                                      !path.startsWith('/direct/') &&
                                      !path.startsWith('/explore/') &&
                                      !path.startsWith('/reels/') &&
                                      !path.startsWith('/stories/');
                if (isNotSpecialRoute) {
                    let isMatch = false;
                    if (link.innerText && link.innerText.toLowerCase().includes('view profile')) {
                        isMatch = true;
                    }
                    else if (/^\/[a-zA-Z0-9_.]+\/?$/.test(path)) {
                        isMatch = true;
                    }

                    if (isMatch) {
                        const username = path.split('/').filter(p => p)[0];
                        if (username) {
                            console.log(`[InstaLogger] SUCCESS: Found username "${username}" (Level ${i}).`);
                            return username;
                        }
                    }
                }
            } catch (e) {
                // Ignore invalid hrefs
            }
        }
        currentElement = currentElement.parentElement;
    }
    console.log("[InstaLogger] Proximity Climber failed. Falling back to URL check.");
    const pagePath = window.location.pathname;
    const pathParts = pagePath.split('/').filter(p => p);
    if (pathParts.length === 1 && !['explore', 'reels', 'inbox', 'direct', 'accounts', 'login'].includes(pathParts[0])) {
        return pathParts[0];
    }
    if (pagePath.includes('/direct/t/')) {
        return "unknown_user_in_thread";
    }
    return "not_in_a_dm_thread";
}

function startStatusRefresh(username) {
    // Clear any existing refresh interval
    stopStatusRefresh();

    // Only start refresh if tab is visible
    if (document.visibilityState !== 'visible') {
        console.log(`[InstaLogger][UI] Tab not visible, skipping refresh start for: ${username}`);
        return;
    }

    // Start periodic refresh
    statusRefreshInterval = setInterval(() => {
        // Only refresh if tab is visible and we're still on the same username
        if (document.visibilityState === 'visible' &&
            lastCheckedUsername === username &&
            !isCheckInProgress) {
            console.log(`[InstaLogger][UI] Periodic refresh for: ${username}`);
            runProfileCheck(username, true); // silent refresh
        }
    }, STATUS_REFRESH_INTERVAL);

    console.log(`[InstaLogger][UI] Started status refresh interval for: ${username}`);
}

function stopStatusRefresh() {
    if (statusRefreshInterval) {
        clearInterval(statusRefreshInterval);
        statusRefreshInterval = null;
        console.log(`[InstaLogger][UI] Stopped status refresh interval`);
    }
}

// Handle tab visibility changes - refresh when tab becomes visible
function handleVisibilityChange() {
    if (document.visibilityState === 'visible' && lastCheckedUsername) {
        console.log(`[InstaLogger][UI] Tab became visible, refreshing status for: ${lastCheckedUsername}`);
        // Do an immediate refresh when tab becomes visible
        if (!isCheckInProgress) {
            runProfileCheck(lastCheckedUsername, true);
        }
        // Restart the refresh interval
        startStatusRefresh(lastCheckedUsername);
    } else if (document.visibilityState === 'hidden') {
        console.log(`[InstaLogger][UI] Tab hidden, pausing refresh`);
        stopStatusRefresh();
    }
}

// Listen for visibility changes
document.addEventListener('visibilitychange', handleVisibilityChange);

async function runProfileCheck(username, silentRefresh = false) {
    if (isCheckInProgress) {
        console.log(`[InstaLogger][UI] Aborting check for ${username} - check in progress.`);
        return;
    }
    isCheckInProgress = true;
    const checkStartedForUsername = username;
    console.log(`[InstaLogger][UI] Starting check for: ${username}${silentRefresh ? ' (silent refresh)' : ''}`);
    lastCheckedUsername = username;

    // Show searching banner initially (only if not a silent refresh)
    if (!silentRefresh) {
        await showStatusBanner('searching', { syncStage: 'local' });
    }

    // Send check request to IPC server via background
    sendMessageToBackground({
        type: 'CHECK_PROSPECT_STATUS',
        payload: { target: username }
    }, async (response) => {
        // Check if user navigated away
        if (lastCheckedUsername !== checkStartedForUsername) {
            console.log(`[InstaLogger][UI] Username changed during check. Aborting.`);
            isCheckInProgress = false;
            return;
        }

        let banner = document.getElementById('insta-warning-banner');

        // Handle error responses
        if (response?.error || response?.success === false) {
            console.error(`[InstaLogger][UI] Error checking status: ${response.message || response.error}`);
            updateSyncStage(banner, 'error');
            isCheckInProgress = false;
            return;
        }

        // Response data is nested under 'data' key from create_ack_response
        const data = response?.data || response;

        if (data?.contacted) {
            console.log(`[InstaLogger][UI] HIT for ${username}, status: ${data.status}`);
            await showStatusBanner('contacted', { status: data.status, syncStage: 'complete' });
        } else {
            console.log(`[InstaLogger][UI] MISS for ${username} - Not contacted before`);
            await showStatusBanner('not_contacted', { syncStage: 'not-found' });
        }

        // Start periodic refresh for this username
        startStatusRefresh(username);

        isCheckInProgress = false;
        console.log(`[InstaLogger][UI] Check complete for ${username}.`);
    });
}

function waitForElement(selector, callback, timeout = 5000, interval = 200) {
    const startTime = Date.now();
    const timer = setInterval(() => {
        const element = document.querySelector(selector);
        if (element) {
            clearInterval(timer);
            callback(element);
        } else if (Date.now() - startTime > timeout) {
            clearInterval(timer);
            console.log(`[InstaLogger] Timed out waiting for element: ${selector}`);
        }
    }, interval);
}

// =============================================================================
// 4. DM Logging Mode Logic
// =============================================================================

async function getActorUsername() {
    try {
        const result = await chrome.storage.local.get('actorUsername');
        return result.actorUsername || 'unknown_actor';
    } catch (e) {
        console.error("[InstaLogger] Error fetching actor username from storage:", e);
        return 'unknown_actor';
    }
}

function getTargetUsername(inputElement) {
    if (!inputElement) return 'unknown_target';
    let currentElement = inputElement;
    for (let i = 0; i < 25 && currentElement; i++) {
        const links = currentElement.querySelectorAll('a[href]');
        for (const link of links) {
            const href = link.getAttribute('href');
            const match = href.match(/^\/([a-zA-Z0-9_.]+)\/$/);
            if (match && match[1] && !['explore', 'direct', 'reels'].includes(match[1])) {
                 if(link.textContent.toLowerCase().includes(match[1].toLowerCase())){
                    return match[1];
                 }
            }
        }
        currentElement = currentElement.parentElement;
    }
    return "unknown_target";
}

async function logOutreach(inputElement) {
    const messageText = inputElement.textContent || inputElement.innerText;
    if (!messageText || !messageText.trim()) return;

    const actorUsername = await getActorUsername();
    const targetUsername = getTargetUsername(inputElement);
    const messageSnippet = messageText.trim().substring(0, 200);

    if (targetUsername === 'unknown_target' || actorUsername === 'unknown_actor') {
        console.error(`[InstaLogger] Aborting log. Target: ${targetUsername}, Actor: ${actorUsername}`);
        return;
    }

    console.log(`[InstaLogger] Logging outreach by ${actorUsername} to @${targetUsername}`);
    sendMessageToBackground({
        type: 'LOG_OUTREACH',
        payload: { target: targetUsername, actor: actorUsername, message: messageSnippet }
    }, (response) => {
        // After message is logged, refresh the banner to show updated status
        const data = response?.data || response;
        if (response?.success || data?.log_id) {
            console.log(`[InstaLogger] Outreach logged successfully, refreshing banner...`);
            // Small delay to let DB update complete, then refresh
            setTimeout(() => {
                if (lastCheckedUsername && !isCheckInProgress) {
                    runProfileCheck(lastCheckedUsername, true);
                }
            }, 500);
        }
    });
}

function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        logOutreach(e.target);
    }
}

function findAndAttach() {
    if (!window.location.pathname.startsWith('/direct/')) {
        if(activeChatInput) {
            activeChatInput.removeEventListener('keydown', handleKeyDown, { capture: true });
            activeChatInput = null;
        }
        return;
    }

    const chatInput = document.querySelector(CHAT_INPUT_SELECTOR);
    if (chatInput && chatInput !== activeChatInput) {
        if (activeChatInput) {
            activeChatInput.removeEventListener('keydown', handleKeyDown, { capture: true });
        }
        chatInput.addEventListener('keydown', handleKeyDown, { capture: true });
        activeChatInput = chatInput;
    }
}

// =============================================================================
// 5. URL Change Handler (Main Router)
// =============================================================================

const handleUrlChange = () => {
    const currentUrl = window.location.href;
    if (currentUrl === lastCheckedUrl) return;

    console.log(`[InstaLogger][UI] URL changed: ${lastCheckedUrl} -> ${currentUrl}`);
    lastCheckedUrl = currentUrl;

    if (isCheckInProgress) {
        console.log("[InstaLogger][UI] Releasing stale lock due to URL change.");
        isCheckInProgress = false;
    }

    // Stop any existing refresh interval
    stopStatusRefresh();

    // Remove any existing banners
    document.querySelectorAll('.insta-warning-banner').forEach(b => b.remove());
    stopBannerPulse();

    const profileRegex = /https:\/\/www\.instagram\.com\/([a-zA-Z0-9_.]+)\/?$/;
    const directRegex = /https:\/\/www\.instagram\.com\/direct\/t\//;
    let username = null;

    const profileMatch = currentUrl.match(profileRegex);
    if (profileMatch && profileMatch[1] && !['explore', 'reels', 'inbox', 'direct', 'accounts', 'login', 'p'].includes(profileMatch[1])) {
        username = profileMatch[1];
        lastCheckedUsername = username;
        runProfileCheck(username);
    } else if (directRegex.test(currentUrl)) {
        showStatusBanner('searching', { syncStage: 'local' });
        waitForElement(CHAT_INPUT_SELECTOR, (chatInput) => {
            const dmUsername = getInstagramUsername(chatInput);
            if (dmUsername && dmUsername !== "unknown_user_in_thread" && dmUsername !== "not_in_a_dm_thread") {
                lastCheckedUsername = dmUsername;
                runProfileCheck(dmUsername);
            }
        });
    }
};

// =============================================================================
// Initialization
// =============================================================================
function initialize() {
    console.log('[InstaLogger] Initializing...');
    connectPort();

    // Check if we are in discovery mode
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('discover_actor') === 'true') {
        runDiscovery();
        return;
    }

    // Set up URL change observer
    const observer = new MutationObserver(() => {
        setTimeout(handleUrlChange, 50);
    });
    observer.observe(document.body, { childList: true, subtree: true });

    // Attach DM logging listeners
    setInterval(findAndAttach, 1000);

    // Run initial check on page load
    setTimeout(() => {
        const currentUrl = window.location.href;
        const profileRegex = /https:\/\/www\.instagram\.com\/([a-zA-Z0-9_.]+)\/?$/;
        const directRegex = /https:\/\/www\.instagram\.com\/direct\/t\//;

        if (isCheckInProgress) {
            isCheckInProgress = false;
        }

        const profileMatch = currentUrl.match(profileRegex);
        if (profileMatch && profileMatch[1] && !['explore', 'reels', 'inbox', 'direct', 'accounts', 'login', 'p'].includes(profileMatch[1])) {
            const username = profileMatch[1];
            console.log(`[InstaLogger][UI] Page load - checking profile: ${username}`);
            lastCheckedUrl = currentUrl;
            lastCheckedUsername = username;
            runProfileCheck(username);
        } else if (directRegex.test(currentUrl)) {
            console.log(`[InstaLogger][UI] Page load - DM thread detected`);
            lastCheckedUrl = currentUrl;
            showStatusBanner('searching', { syncStage: 'local' });
            waitForElement(CHAT_INPUT_SELECTOR, (chatInput) => {
                const dmUsername = getInstagramUsername(chatInput);
                if (dmUsername && dmUsername !== "unknown_user_in_thread" && dmUsername !== "not_in_a_dm_thread") {
                    lastCheckedUsername = dmUsername;
                    runProfileCheck(dmUsername);
                }
            });
        }
    }, 300);
}

initialize();
