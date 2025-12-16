// The connection to the native messaging host
let nativePort = null;
// The connection to the content script
let contentPort = null;

const NATIVE_HOST_NAME = 'com.instaoutreach.logger';
let discoveryTabId = null;

console.log('Background script started (v2 - with Profile Discovery).');

// --- Profile Discovery on Install/Update ---
chrome.runtime.onInstalled.addListener((details) => {
    if (details.reason === 'install' || details.reason === 'update') {
        console.log('Extension installed/updated. Checking for Actor username...');
        // Check if the username already exists
        chrome.storage.local.get('actorUsername', (result) => {
            if (!result.actorUsername) {
                console.log('Actor username not found in storage. Starting discovery process.');
                // Use a query parameter to signal to the content script that we are in discovery mode
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
    console.assert(port.name === 'content-script', 'Connection is not from content script');
    contentPort = port;
    console.log('Connected to content script.');

    contentPort.onMessage.addListener((message) => {
        // --- Handle messages from the content script ---
        
        // This is our new message type for the discovery process
        if (message.type === 'FOUND_ACTOR_USERNAME') {
            const username = message.username;
            console.log(`Received username from discovery: ${username}`);
            if (username && username !== 'unknown_actor') {
                chrome.storage.local.set({ actorUsername: username }, () => {
                    console.log(`Successfully saved actor username: ${username}`);
                    // Close the discovery tab now that we're done
                    if (discoveryTabId) {
                        chrome.tabs.remove(discoveryTabId);
                        discoveryTabId = null;
                    }
                });
            }
            return; // Stop here, don't forward this to native host
        }

        // Forward all other messages to the native host
        if (nativePort) {
            console.log('Forwarding message from content script to native host:', message);
            nativePort.postMessage(message);
        } else {
            console.error('Cannot forward message: Native host not connected.');
            // Attempt to reconnect if the native host is down
            connectNative();
        }
    });

    contentPort.onDisconnect.addListener(() => {
        console.log('Content script disconnected.');
        contentPort = null;
    });
});


// --- Connection to Native Host ---
function connectNative() {
    console.log(`Connecting to native host: ${NATIVE_HOST_NAME}`);
    nativePort = chrome.runtime.connectNative(NATIVE_HOST_NAME);

    nativePort.onMessage.addListener((message) => {
        if (contentPort) {
            contentPort.postMessage(message);
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