/**
 * Insta Outreach Logger - Injector Script (v11 - Debug)
 *
 * This script polls for the page's main data scripts and uses a reliable
 * regex to find a user object pattern (username + fbid) to extract the
 * logged-in user's username.
 */
(function() {
    
    const maxAttempts = 50; // Try for 5 seconds
    let attempts = 0;
    console.log('[InstaLogger Injector DEBUG] Injector script started.');

    const findUsernameInterval = setInterval(() => {
        attempts++;
        let usernameFound = null;
        console.log(`[InstaLogger Injector DEBUG] Polling attempt ${attempts}/${maxAttempts}...`);

        try {
            const userObjectRegex = /"username":"([a-zA-Z0-9_.]+)","fbid":"\d+"/;
            
            const scripts = document.querySelectorAll('script');
            
            for (const script of scripts) {
                if (script.textContent) {
                    console.log(`[InstaLogger Injector DEBUG] Applying regex to script content (first 100 chars): ${script.textContent.substring(0, 100)}...`);
                    const match = script.textContent.match(userObjectRegex);
                    if (match && match[1]) {
                        usernameFound = match[1];
                        console.log(`[InstaLogger Injector DEBUG] Regex matched! Found username: ${usernameFound}`);
                        break; 
                    }
                }
            }

            if (usernameFound) {
                clearInterval(findUsernameInterval);
                console.log(`[InstaLogger Injector DEBUG] Posting message to content script with username: ${usernameFound}`);
                window.postMessage({ type: 'FROM_INSTA_PAGE_ACTOR', actorUsername: usernameFound }, '*');
            } else if (attempts > maxAttempts) {
                clearInterval(findUsernameInterval);
                console.log('[InstaLogger Injector DEBUG] Max attempts reached, username not found.');
            }
        } catch (e) {
            console.error('[InstaLogger Injector DEBUG] An error occurred in polling interval:', e);
            clearInterval(findUsernameInterval);
        }

    }, 100);

})();