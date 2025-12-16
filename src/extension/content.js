/**
 * Insta Outreach Logger - Content Script (v10 - Profile Discovery Workflow)
 * 
 * This script has two modes:
 * 1. Discovery Mode: If on instagram.com homepage, it finds the user's
 *    profile link and sends the username to the background script.
 * 2. Logging Mode: On DM pages, it reads the saved username from storage
 *    and logs messages as usual.
 */

console.log('[InstaLogger] Content Script Loaded (v10 - Profile Discovery)');

// =============================================================================
// Globals & Background Communication
// =============================================================================
let activeChatInput = null;
const port = chrome.runtime.connect({ name: 'content-script' });

function sendMessageToBackground(data) {
    try {
        port.postMessage(data);
    } catch (e) {
        // This can happen if the port disconnects, it's not a critical error
    }
}

// =============================================================================
// 1. Discovery Mode Logic
// =============================================================================
function runDiscovery() {
    console.log('[InstaLogger] Running in Discovery Mode...');
    let attempts = 0;
    const maxAttempts = 50; // Try for 5 seconds

    const discoveryInterval = setInterval(() => {
        attempts++;
        // Use a selector that targets the navigation rail's "Profile" link
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
                console.log(`[InstaLogger] Discovery SUCCESS: Found username "${username}". Sending to background.`);
                // Send to background script to save and close tab
                port.postMessage({ type: 'FOUND_ACTOR_USERNAME', username: username });
            }
        } else if (attempts > maxAttempts) {
            clearInterval(discoveryInterval);
            console.error('[InstaLogger] Discovery FAILED: Could not find profile link after 5 seconds.');
        }
    }, 100);
}


// =============================================================================
// 2. Logging Mode Logic
// =============================================================================

/**
 * Retrieves the actor username from chrome's local storage.
 * @returns {Promise<string>} A promise that resolves to the actor's username.
 */
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

    // Must now await the username from storage
    const actorUsername = await getActorUsername();
    const targetUsername = getTargetUsername(inputElement);
    const messageSnippet = messageText.trim().substring(0, 200);

    if (targetUsername === 'unknown_target' || actorUsername === 'unknown_actor') {
        console.error(`[InstaLogger] Aborting log. Target: ${targetUsername}, Actor: ${actorUsername}`);
        // Optional: Trigger discovery again if actor is unknown
        if (actorUsername === 'unknown_actor') {
            console.log("[InstaLogger] Actor is unknown, you may need to restart the browser or trigger discovery manually.");
        }
        return;
    }
    
    console.log(`[InstaLogger] Logging outreach by ${actorUsername} to @${targetUsername}`);
    sendMessageToBackground({
        type: 'LOG_OUTREACH',
        payload: { target: targetUsername, actor: actorUsername, message: messageSnippet }
    });
}

function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        logOutreach(e.target);
    }
}

function findAndAttach() {
    // Only attach listeners if we are on a DM page
    if (!window.location.pathname.startsWith('/direct/')) {
        if(activeChatInput) {
            activeChatInput.removeEventListener('keydown', handleKeyDown, { capture: true });
            activeChatInput = null;
        }
        return;
    }

    const chatInput = document.querySelector('div[role="textbox"][aria-label="Message"]');
    if (chatInput && chatInput !== activeChatInput) {
        if (activeChatInput) {
            activeChatInput.removeEventListener('keydown', handleKeyDown, { capture: true });
        }
        chatInput.addEventListener('keydown', handleKeyDown, { capture: true });
        activeChatInput = chatInput;
    }
}

// =============================================================================
// Initialization
// =============================================================================
function initialize() {
    console.log('[InstaLogger] Initializing...');

    // Check if we are in discovery mode
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('discover_actor') === 'true') {
        runDiscovery();
    } else {
        // Normal operation: attach listeners for DM page
        setInterval(findAndAttach, 1000);
    }
}

initialize();
