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
const STATUS_REFRESH_INTERVAL = 30000; // Refresh status every 30 seconds
const ACTOR_CHECK_INTERVAL = 5000; // Check for account switches every 5 seconds

let activeChatInput = null;
let lastCheckedUrl = '';
let lastCheckedUsername = '';
let isCheckInProgress = false;
let bannerPulseInterval = null;
let statusRefreshInterval = null;
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

/**
 * Scrapes the current viewer's username from the Instagram sidebar/navigation.
 * This is used for periodic verification that the logged-in account hasn't changed.
 */
function scrapeCurrentViewerUsername() {
    // Strategy 1: Look for profile link in the navigation sidebar
    const profileLinks = Array.from(document.querySelectorAll('a[href^="/"]'));

    for (const link of profileLinks) {
        const href = link.getAttribute('href');
        if (!href) continue;

        // Look for links that have a profile image inside them (usually the nav profile link)
        const hasProfileImg = link.querySelector('img[alt*="profile" i]') ||
                             link.querySelector('img[data-testid="user-avatar"]');

        if (hasProfileImg) {
            const match = href.match(/^\/([a-zA-Z0-9_.]+)\/?$/);
            if (match && match[1] && !['explore', 'reels', 'inbox', 'direct', 'accounts', 'p'].includes(match[1])) {
                return match[1];
            }
        }

        // Look for "Profile" text link
        if (link.textContent.trim().toLowerCase() === 'profile') {
            const match = href.match(/^\/([a-zA-Z0-9_.]+)\/?$/);
            if (match && match[1]) {
                return match[1];
            }
        }
    }

    // Strategy 2: Check for the more options menu that contains profile link
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

/**
 * Handles actor username switching.
 * Called when we detect the logged-in account has changed.
 */
async function handleActorSwitch(newUsername) {
    console.log(`[InstaLogger][Actor] Account switch detected: ${currentActorUsername} -> ${newUsername}`);

    // Update the cached value
    currentActorUsername = newUsername;

    // Save to chrome storage
    await chrome.storage.local.set({ actorUsername: newUsername });

    // Notify the background script
    sendMessageToBackground({
        type: 'ACTOR_SWITCH',
        payload: { old_actor: currentActorUsername, new_actor: newUsername }
    });

    // Refresh the current banner if we're on a profile/DM page
    if (lastCheckedUsername && !isCheckInProgress) {
        console.log(`[InstaLogger][Actor] Refreshing banner for ${lastCheckedUsername} with new actor ${newUsername}`);
        runProfileCheck(lastCheckedUsername, true);
    }
}

/**
 * Periodically checks if the logged-in actor has changed (account switching).
 * Instagram is an SPA, so users can switch accounts without a page reload.
 */
async function checkForActorSwitch() {
    const scrapedUsername = scrapeCurrentViewerUsername();

    if (!scrapedUsername) {
        // Could not determine current user, skip this check
        return;
    }

    // Get stored actor username
    const stored = await chrome.storage.local.get('actorUsername');
    const storedUsername = stored.actorUsername;

    // Initialize currentActorUsername if not set
    if (!currentActorUsername && storedUsername) {
        currentActorUsername = storedUsername;
    }

    // Check for mismatch
    if (storedUsername && scrapedUsername !== storedUsername) {
        console.log(`[InstaLogger][Actor] Mismatch detected: stored=${storedUsername}, scraped=${scrapedUsername}`);
        await handleActorSwitch(scrapedUsername);
    } else if (!storedUsername && scrapedUsername) {
        // First time setup - save the scraped username
        console.log(`[InstaLogger][Actor] First-time actor discovery: ${scrapedUsername}`);
        currentActorUsername = scrapedUsername;
        await chrome.storage.local.set({ actorUsername: scrapedUsername });
        sendMessageToBackground({ type: 'FOUND_ACTOR_USERNAME', username: scrapedUsername });
    }
}

/**
 * Starts the periodic actor verification check.
 */
function startActorVerification() {
    if (actorCheckInterval) {
        clearInterval(actorCheckInterval);
    }

    // Initial check
    setTimeout(checkForActorSwitch, 1000);

    // Periodic checks
    actorCheckInterval = setInterval(checkForActorSwitch, ACTOR_CHECK_INTERVAL);
    console.log('[InstaLogger][Actor] Started periodic actor verification');
}

/**
 * Stops the periodic actor verification.
 */
function stopActorVerification() {
    if (actorCheckInterval) {
        clearInterval(actorCheckInterval);
        actorCheckInterval = null;
    }
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

    const allStages = ['sync-stage-local', 'sync-stage-cloud', 'sync-stage-downloading', 'sync-stage-complete', 'sync-stage-not-found', 'sync-stage-error', 'sync-stage-detection-failed'];
    banner.classList.remove(...allStages);

    if (stage) {
        banner.classList.add(`sync-stage-${stage}`);
        console.log(`[InstaLogger][UI] Sync stage updated: ${stage}`);

        if (stage === 'local') startBannerPulse(banner, 245, 158, 11);
        else if (stage === 'downloading') startBannerPulse(banner, 16, 185, 129);
        else if (stage === 'error') startBannerPulse(banner, 239, 68, 68);
        else if (stage === 'detection-failed') startBannerPulse(banner, 255, 69, 0);
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
        if(data.syncStage === 'detection-failed') {
             startBannerPulse(banner, 255, 69, 0);
        }
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

    // REMOVED: Automatic cleanup of 'searching' banner. 
    // It should stay until success or explicit failure.
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
    
    // Strategy 1: Climb up from input element (Legacy, good for active chats)
    if (inputElement) {
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
    }

    // Strategy 2: Header Scraping (Fallback for "Message Request Sent" or missing input)
    console.log("[InstaLogger] Proximity Climber failed. Trying Header Scraping...");
    
    // Try to find the chat header. It's usually a header tag or a specific div at the top of main.
    // We look for a link that looks like a profile link inside the main content area.
    const mainContent = document.querySelector('div[role="main"]');
    if (mainContent) {
        const headerLinks = mainContent.querySelectorAll('header a[href^="/"]');
        for (const link of headerLinks) {
             const href = link.getAttribute('href');
             // Validate it's a profile link (not /direct, /explore, etc.)
             const match = href.match(/^\/([a-zA-Z0-9_.]+)\/?$/);
             if (match && match[1] && !['explore', 'direct', 'reels', 'stories'].includes(match[1])) {
                 console.log(`[InstaLogger] SUCCESS: Found username "${match[1]}" in header.`);
                 return match[1];
             }
        }
        
        // Sometimes the header doesn't use <header>, look for the first H2 or active element
        const headerTitle = mainContent.querySelector('h2');
        if (headerTitle) {
            const text = headerTitle.textContent;
            // Simple validation: username usually doesn't have spaces (unless it's a full name, but header is usually username)
            // Actually, Instagram header often shows Full Name or Username.
            // Let's rely on the link wrapper usually present around the image or name.
            const parentLink = headerTitle.closest('a');
            if (parentLink) {
                 const href = parentLink.getAttribute('href');
                 const match = href.match(/^\/([a-zA-Z0-9_.]+)\/?$/);
                 if (match && match[1]) return match[1];
            }
        }
    }

    // Fallback: URL check
    console.log("[InstaLogger] Header Scraping failed. Falling back to URL check.");
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

function waitForElement(selector, callback, timeout = 5000, interval = 200, onTimeout = null) {
    const startTime = Date.now();
    const timer = setInterval(() => {
        const element = document.querySelector(selector);
        if (element) {
            clearInterval(timer);
            callback(element);
        } else if (Date.now() - startTime > timeout) {
            clearInterval(timer);
            console.log(`[InstaLogger] Timed out waiting for element: ${selector}`);
            if (onTimeout) onTimeout();
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
    if (!inputElement) return null; // Return null instead of 'unknown_target' for easier fallback check
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
    return null;
}

async function logOutreach(inputElement) {
    const messageText = inputElement.textContent || inputElement.innerText;
    if (!messageText || !messageText.trim()) return;

    const actorUsername = await getActorUsername();
    
    // Primary strategy: Proximity climb (rarely works in DMs due to DOM structure)
    let targetUsername = getTargetUsername(inputElement);
    
    // Fallback strategy: Use the globally tracked username from the banner check
    // This is much more reliable in DMs because we found it from the Header
    if (!targetUsername && lastCheckedUsername && lastCheckedUsername !== "unknown_target" && lastCheckedUsername !== "not_in_a_dm_thread") {
        console.log(`[InstaLogger] Proximity climb failed. Using cached username: ${lastCheckedUsername}`);
        targetUsername = lastCheckedUsername;
    }

    const messageSnippet = messageText.trim().substring(0, 200);

    if (!targetUsername || targetUsername === 'unknown_target' || actorUsername === 'unknown_actor') {
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
        console.log("[InstaLogger] Attached logging listener to chat input.");
    }
}

// =============================================================================
// 5. URL Change Handler (Main Router)
// =============================================================================

let dmDiscoveryInterval = null;

const handleUrlChange = () => {
    const currentUrl = window.location.href;
    if (currentUrl === lastCheckedUrl) return;

    console.log(`[InstaLogger][UI] URL changed: ${lastCheckedUrl} -> ${currentUrl}`);
    lastCheckedUrl = currentUrl;

    if (isCheckInProgress) {
        console.log("[InstaLogger][UI] Releasing stale lock due to URL change.");
        isCheckInProgress = false;
    }

    // Stop any existing refresh interval or DM discovery
    stopStatusRefresh();
    if (dmDiscoveryInterval) {
        clearInterval(dmDiscoveryInterval);
        dmDiscoveryInterval = null;
    }

    // Remove any existing banners
    document.querySelectorAll('.insta-warning-banner').forEach(b => b.remove());
    stopBannerPulse();

    const profileRegex = /https:\/\/www\.instagram\.com\/([a-zA-Z0-9_.]+)\/?$/;
    const directRegex = /https:\/\/www\.instagram\.com\/direct\/t\//;
    let username = null;

    const profileMatch = currentUrl.match(profileRegex);
    
    // --- CASE 1: Profile Page ---
    if (profileMatch && profileMatch[1] && !['explore', 'reels', 'inbox', 'direct', 'accounts', 'login', 'p'].includes(profileMatch[1])) {
        username = profileMatch[1];
        lastCheckedUsername = username;
        runProfileCheck(username);
    } 
    // --- CASE 2: Direct Message Thread ---
    else if (directRegex.test(currentUrl)) {
        showStatusBanner('searching', { syncStage: 'local' });
        
        console.log("[InstaLogger] Entered DM Thread. Starting username polling...");
        
        let attempts = 0;
        const maxAttempts = 20; // 10 seconds (20 * 500ms)
        
        // Start polling for the username
        // We poll because the DOM might not have updated the header yet
        dmDiscoveryInterval = setInterval(() => {
            attempts++;
            
            // Check if user navigated away while polling
            if (window.location.href !== currentUrl) {
                clearInterval(dmDiscoveryInterval);
                return;
            }

            // Use a more generic selector for the chat container to ensure we don't fail just because input is missing
            const chatContainer = document.querySelector('div[role="main"]');
            const chatInput = document.querySelector(CHAT_INPUT_SELECTOR);
            
            // Try to find username
            const dmUsername = getInstagramUsername(chatInput || chatContainer);
            
            if (dmUsername && 
                dmUsername !== "unknown_user_in_thread" && 
                dmUsername !== "not_in_a_dm_thread") {
                
                // SUCCESS
                console.log(`[InstaLogger] Polling SUCCESS: Found DM username "${dmUsername}" after ${attempts} attempts.`);
                clearInterval(dmDiscoveryInterval);
                dmDiscoveryInterval = null;
                
                lastCheckedUsername = dmUsername;
                runProfileCheck(dmUsername);
                
            } else if (attempts >= maxAttempts) {
                // FAILURE
                console.log("[InstaLogger] Polling FAILED: Could not detect username in DM thread.");
                clearInterval(dmDiscoveryInterval);
                dmDiscoveryInterval = null;
                
                const banner = document.getElementById('insta-warning-banner');
                updateSyncStage(banner, 'detection-failed');
            }
        }, 500); // Check every 500ms
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

    // Start hardened actor verification (detects account switching)
    startActorVerification();

    // Set up URL change observer for SPA navigation
    const observer = new MutationObserver(() => {
        setTimeout(handleUrlChange, 50);
    });
    observer.observe(document.body, { childList: true, subtree: true });

    // Also observe for significant DOM changes that might indicate account switch
    const accountSwitchObserver = new MutationObserver((mutations) => {
        // Look for mutations that might indicate account switch
        // (e.g., navigation rail changes, profile picture changes)
        for (const mutation of mutations) {
            if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                for (const node of mutation.addedNodes) {
                    if (node.nodeType === Node.ELEMENT_NODE) {
                        // Check if this is a nav element or contains user info
                        if (node.matches && (
                            node.matches('nav') ||
                            node.querySelector && node.querySelector('img[alt*="profile" i]')
                        )) {
                            // Trigger an actor check
                            setTimeout(checkForActorSwitch, 500);
                            return;
                        }
                    }
                }
            }
        }
    });

    // Observe the nav/sidebar area specifically if it exists
    const navElement = document.querySelector('nav') || document.body;
    accountSwitchObserver.observe(navElement, { childList: true, subtree: true });

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
            
             // Use a more generic selector for the chat container to ensure we don't fail just because input is missing
            const CHAT_CONTAINER = 'div[role="main"]';
            
            waitForElement(CHAT_CONTAINER, (element) => {
                const chatInput = document.querySelector(CHAT_INPUT_SELECTOR);
                const dmUsername = getInstagramUsername(chatInput || element);
                if (dmUsername && dmUsername !== "unknown_user_in_thread" && dmUsername !== "not_in_a_dm_thread") {
                    lastCheckedUsername = dmUsername;
                    runProfileCheck(dmUsername);
                } else {
                     console.log("[InstaLogger] Could not detect username in DM thread (Page Load).");
                     const banner = document.getElementById('insta-warning-banner');
                     updateSyncStage(banner, 'detection-failed');
                }
            }, 5000, 200, () => {
                // Timeout callback
                console.log("[InstaLogger] Timeout waiting for chat container (Page Load).");
                const banner = document.getElementById('insta-warning-banner');
                updateSyncStage(banner, 'detection-failed');
            });
        }
    }, 300);
}

initialize();
