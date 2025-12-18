// The connection to the native messaging host
let nativePort = null;
// Map of content script ports by tab ID
let contentPorts = new Map();
// Map of pending requests awaiting native host response
let pendingRequests = new Map();

const NATIVE_HOST_NAME = 'com.instaoutreach.logger';
let discoveryTabId = null;

console.log('Background script started (v3 - with Real-Time Status Check).');

// --- Profile Discovery on Install/Update ---
chrome.runtime.onInstalled.addListener((details) => {
    if (details.reason === 'install' || details.reason === 'update') {
        console.log('Extension installed/updated. Checking for Actor username...');
        chrome.storage.local.get('actorUsername', (result) => {
            if (!result.actorUsername) {
                console.log('Actor username not found in storage. Starting discovery process.');
                chrome.tabs.create({ url: 'https://www.instagram.com/?discover_actor=true' }, (tab) => {
                    discoveryTabId = tab.id;
                });
            } else {
                console.log(`Actor username already set: ${result.actorUsername}`);
            }
        });
    }
});


// --- Connection to Content Script ---
chrome.runtime.onConnect.addListener((port) => {
    if (port.name !== 'content-script') return;

    const tabId = port.sender?.tab?.id;
    if (tabId) {
        contentPorts.set(tabId, port);
    }
    console.log(`Connected to content script (tab ${tabId}).`);

    port.onMessage.addListener((message) => {
        // Handle actor discovery
        if (message.type === 'FOUND_ACTOR_USERNAME') {
            const username = message.username;
            console.log(`Received username from discovery: ${username}`);
            if (username && username !== 'unknown_actor') {
                chrome.storage.local.set({ actorUsername: username }, () => {
                    console.log(`Successfully saved actor username: ${username}`);
                    if (discoveryTabId) {
                        chrome.tabs.remove(discoveryTabId);
                        discoveryTabId = null;
                    } else {
                        // Fallback: Find tab by URL if ID is lost (e.g. service worker restart)
                        chrome.tabs.query({ url: "https://www.instagram.com/?discover_actor=true" }, (tabs) => {
                            if (tabs && tabs.length > 0) {
                                chrome.tabs.remove(tabs[0].id);
                            }
                        });
                    }
                });
            }
            return;
        }

        // Store request info for response routing
        if (message.requestId) {
            let context = {};
            if (message.type === 'CHECK_PROSPECT_STATUS' && message.payload?.target) {
                context.target = message.payload.target;
            }
            pendingRequests.set(message.requestId, { tabId, requestId: message.requestId, context });
        }

        // Forward all other messages to the native host
        if (nativePort) {
            console.log('Forwarding message to native host:', message.type);
            nativePort.postMessage(message);
        } else {
            console.error('Cannot forward message: Native host not connected.');
            // Send error response back to content script
            if (message.requestId && tabId) {
                port.postMessage({
                    requestId: message.requestId,
                    error: true,
                    message: 'Native host not connected'
                });
            }
            connectNative();
        }
    });

    port.onDisconnect.addListener(() => {
        console.log(`Content script disconnected (tab ${tabId}).`);
        if (tabId) {
            contentPorts.delete(tabId);
        }
    });
});


// --- Connection to Native Host ---
function connectNative() {
    console.log(`Connecting to native host: ${NATIVE_HOST_NAME}`);
    try {
        nativePort = chrome.runtime.connectNative(NATIVE_HOST_NAME);

        nativePort.onMessage.addListener((message) => {
            // console.log('Received message from native host:', message); // Reduced verbosity

            // Route response to the correct content script
            if (message.requestId && pendingRequests.has(message.requestId)) {
                const { tabId, requestId, context } = pendingRequests.get(message.requestId);
                pendingRequests.delete(message.requestId);

                // Log detailed response if we have context
                if (context && context.target) {
                     const data = message.data || message;
                     console.log(`[InstaLogger][UI] Check Response for ${context.target}:`, data);
                }

                const port = contentPorts.get(tabId);
                if (port) {
                    port.postMessage(message);
                }
            } else {
                // Broadcast to all connected content scripts if no specific target
                contentPorts.forEach((port) => {
                    try {
                        port.postMessage(message);
                    } catch (e) {
                        // Port may have disconnected
                    }
                });
            }
        });

        nativePort.onDisconnect.addListener(() => {
            const error = chrome.runtime.lastError;
            if (error) {
                console.error('Native host disconnected with error:', error.message);
            } else {
                console.log('Native host disconnected.');
            }
            nativePort = null;
        });
    } catch (e) {
        console.error('Failed to connect to native host:', e);
        nativePort = null;
    }
}

// Initial connection attempt
connectNative();

// Keep-alive interval
setInterval(() => {
    if (nativePort) {
        nativePort.postMessage({ keep_alive: true });
    } else {
        connectNative();
    }
}, 295 * 1000);