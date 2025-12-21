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

        // Handle request for discovery (triggered when content script can't find actor)
        if (message.type === 'REQUEST_ACTOR_DISCOVERY') {
            console.log('Content script requested actor discovery.');
            chrome.storage.local.get('actorUsername', (result) => {
                if (result.actorUsername) {
                    console.log('Actor username already exists, ignoring discovery request.');
                    return;
                }
                
                chrome.tabs.query({ url: "https://www.instagram.com/?discover_actor=true" }, (tabs) => {
                    if (tabs && tabs.length > 0) {
                        console.log('Discovery tab already open.');
                        return;
                    }
                    
                    console.log('Opening discovery tab...');
                    chrome.tabs.create({ url: 'https://www.instagram.com/?discover_actor=true', active: false }, (tab) => {
                        discoveryTabId = tab.id;
                    });
                });
            });
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
            // Attempt to connect
            connectNative();
            
            // If still not connected after attempt, return a friendly error
            if (!nativePort && message.requestId && tabId) {
                port.postMessage({
                    requestId: message.requestId,
                    error: true,
                    message: 'APPLICATION_OFFLINE',
                    friendlyMessage: 'Application not running. Please ensure the Insta Outreach Logger app is open on your computer.'
                });
            } else if (nativePort) {
                nativePort.postMessage(message);
            }
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
    // If already connected, do nothing
    if (nativePort) return;

    console.log(`Attempting to connect to native host: ${NATIVE_HOST_NAME}`);
    try {
        nativePort = chrome.runtime.connectNative(NATIVE_HOST_NAME);

        nativePort.onMessage.addListener((message) => {
            // Route response to the correct content script
            if (message.requestId && pendingRequests.has(message.requestId)) {
                const { tabId, requestId, context } = pendingRequests.get(message.requestId);
                pendingRequests.delete(message.requestId);

                if (context && context.target) {
                     const data = message.data || message;
                     console.log(`[InstaLogger][UI] Check Response for ${context.target}:`, data);
                }

                const port = contentPorts.get(tabId);
                if (port) {
                    port.postMessage(message);
                }
            } else {
                contentPorts.forEach((port) => {
                    try { port.postMessage(message); } catch (e) {}
                });
            }
        });

        nativePort.onDisconnect.addListener(() => {
            const error = chrome.runtime.lastError;
            if (error) {
                // Check if this is a "Host not found" error which usually means setup isn't done
                if (error.message.includes("host not found")) {
                    console.log('[InstaLogger] Native host not registered yet. This is normal during first-time setup.');
                } else {
                    console.warn('[InstaLogger] Native host disconnected:', error.message);
                }
            } else {
                console.log('[InstaLogger] Native host connection closed.');
            }
            nativePort = null;
        });
    } catch (e) {
        // This catch block handles immediate failures in connectNative
        console.log('[InstaLogger] Connection attempt failed (app likely closed).');
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