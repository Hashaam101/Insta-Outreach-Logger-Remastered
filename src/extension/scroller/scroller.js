// DM Scroller - Auto scroll through Instagram DM conversation list
// Remastered v2.4 - Fixed Start Button (Removed Worker) & Enhanced Event Triggering

(function() {
    console.log('[InstaLogger][Scroller] Module Loaded');

    // =============================================================================
    // Constants & State
    // =============================================================================
    
    const DEFAULT_SETTINGS = {
        speed: 'medium', // slow, medium, fast
        direction: 'down' // down, up
    };

    const PRESETS = {
        slow: { pixelsPerSecond: 200 },   
        medium: { pixelsPerSecond: 500 }, 
        fast: { pixelsPerSecond: 1000 }   
    };

    let settings = { ...DEFAULT_SETTINGS };
    let isScrolling = false;
    let scrollInterval = null;
    let panel = null;
    let toggleBtn = null;
    let statusDot = null;
    let statusText = null;
    let startBtn = null;
    
    // Background Scroll State
    let lastTickTime = 0;
    let scrollAccumulator = 0;

    // =============================================================================
    // UI Construction
    // =============================================================================

    function createToggleButton() {
        if (document.getElementById('dm-scroller-toggle-btn')) return;
        
        toggleBtn = document.createElement('button');
        toggleBtn.id = 'dm-scroller-toggle-btn';
        toggleBtn.innerHTML = '📜';
        toggleBtn.title = 'Open DM Scroller';
        toggleBtn.style.display = 'none'; // Hidden by default, shown on /direct/
        
        toggleBtn.addEventListener('click', togglePanel);
        document.body.appendChild(toggleBtn);
        
        // Add pulse animation on creation to draw attention
        toggleBtn.classList.add('pulse-once');
        setTimeout(() => {
            if (toggleBtn) toggleBtn.classList.remove('pulse-once');
        }, 3000);
    }

    function createPanel() {
        if (document.getElementById('dm-scroller-panel')) {
            panel = document.getElementById('dm-scroller-panel');
            return;
        }

        const isMinimized = false;
        const panelHtml = `
            <div id="dm-scroller-panel" ${isMinimized ? 'class="minimized"' : ''}>
                <div class="scroller-header">
                    <div class="scroller-header-title">
                        <span>DM Scroller</span>
                    </div>
                    <div class="scroller-header-actions">
                        <button class="scroller-header-btn" id="scroller-minimize" title="Minimize">−</button>
                        <button class="scroller-header-btn" id="scroller-close" title="Close">×</button>
                    </div>
                </div>
                <div class="scroller-body">
                    <div class="scroller-status">
                        <span class="scroller-status-dot" id="scroller-status-dot"></span>
                        <span id="scroller-status-text">Status: Stopped</span>
                    </div>

                    <div class="scroller-group">
                        <label class="scroller-label">Scroll Speed</label>
                        <select class="scroller-select" id="scroller-speed">
                            <option value="slow">Slow (Normal)</option>
                            <option value="medium">Medium (Fast)</option>
                            <option value="fast">Fast (Turbo)</option>
                        </select>
                    </div>

                    <div class="scroller-group">
                        <label class="scroller-label">Direction</label>
                        <div class="scroller-direction">
                            <button class="scroller-direction-btn" id="scroller-dir-down">
                                <span>↓</span> Down
                            </button>
                            <button class="scroller-direction-btn" id="scroller-dir-up">
                                <span>↑</span> Up
                            </button>
                        </div>
                    </div>

                    <div class="scroller-actions">
                        <button class="scroller-btn scroller-btn-secondary" id="scroller-to-top" title="Scroll to Top">
                            <span>↑↑</span> Top
                        </button>
                        <button class="scroller-btn scroller-btn-start" id="scroller-start">
                            <span>▶</span> Start
                        </button>
                        <button class="scroller-btn scroller-btn-secondary" id="scroller-to-bottom" title="Scroll to Bottom">
                            <span>↓↓</span> Bottom
                        </button>
                    </div>
                </div>
            </div>
        `;

        const div = document.createElement('div');
        div.innerHTML = panelHtml;
        document.body.appendChild(div.firstElementChild);

        // Bind elements
        panel = document.getElementById('dm-scroller-panel');
        statusDot = document.getElementById('scroller-status-dot');
        statusText = document.getElementById('scroller-status-text');
        startBtn = document.getElementById('scroller-start');

        // Make draggable
        makeDraggable(panel);

        // Event Listeners
        document.getElementById('scroller-minimize').addEventListener('click', toggleMinimize);
        document.getElementById('scroller-close').addEventListener('click', () => {
             panel.style.display = 'none';
             stopScrolling();
        });

        document.getElementById('scroller-speed').addEventListener('change', (e) => {
            settings.speed = e.target.value;
            saveSettings();
        });

        document.getElementById('scroller-dir-down').addEventListener('click', () => setDirection('down'));
        document.getElementById('scroller-dir-up').addEventListener('click', () => setDirection('up'));

        document.getElementById('scroller-to-top').addEventListener('click', scrollToTop);
        document.getElementById('scroller-start').addEventListener('click', toggleScrolling);
        document.getElementById('scroller-to-bottom').addEventListener('click', scrollToBottom);

        loadSettings();
    }

    function makeDraggable(element) {
        let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
        const header = element.querySelector('.scroller-header');
        
        header.onmousedown = dragMouseDown;

        function dragMouseDown(e) {
            e = e || window.event;
            e.preventDefault();
            pos3 = e.clientX;
            pos4 = e.clientY;
            document.onmouseup = closeDragElement;
            document.onmousemove = elementDrag;
            element.classList.add('dragging');
        }

        function elementDrag(e) {
            e = e || window.event;
            e.preventDefault();
            pos1 = pos3 - e.clientX;
            pos2 = pos4 - e.clientY;
            pos3 = e.clientX;
            pos4 = e.clientY;
            element.style.top = (element.offsetTop - pos2) + "px";
            element.style.left = (element.offsetLeft - pos1) + "px";
            element.style.right = 'auto'; // Clear right if set
        }

        function closeDragElement() {
            document.onmouseup = null;
            document.onmousemove = null;
            element.classList.remove('dragging');
        }
    }

    // =============================================================================
    // Logic
    // =============================================================================

    function loadSettings() {
        chrome.storage.local.get(['scrollerSettings'], (result) => {
            if (result.scrollerSettings) {
                settings.speed = result.scrollerSettings.speed || DEFAULT_SETTINGS.speed;
                settings.direction = result.scrollerSettings.direction || DEFAULT_SETTINGS.direction;
                updateUI();
            }
        });
    }

    function saveSettings() {
        chrome.storage.local.set({ scrollerSettings: settings });
    }

    function updateUI() {
        if (!panel) return;
        document.getElementById('scroller-speed').value = settings.speed;
        setDirection(settings.direction, false);
    }

    function setDirection(dir, save = true) {
        settings.direction = dir;
        const downBtn = document.getElementById('scroller-dir-down');
        const upBtn = document.getElementById('scroller-dir-up');
        
        if (dir === 'down') {
            downBtn.classList.add('active');
            upBtn.classList.remove('active');
        } else {
            upBtn.classList.add('active');
            downBtn.classList.remove('active');
        }
        if (save) saveSettings();
    }

    function toggleMinimize() {
        panel.classList.toggle('minimized');
    }

    function togglePanel() {
        if (!panel) createPanel();
        panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
        if (panel.style.display === 'block') {
             loadSettings();
        }
    }

    function toggleScrolling() {
        if (isScrolling) {
            stopScrolling();
        } else {
            startScrolling();
        }
    }

    // =============================================================================
    // Scrolling Logic (The Core)
    // =============================================================================

    function findDMContainer() {
        // Strategy 1: Div with role="grid" (Typical for DM list)
        const grids = document.querySelectorAll('div[role="grid"]');
        for (const grid of grids) {
            const rect = grid.getBoundingClientRect();
            // DM list is usually narrow sidebar
            if (rect.width > 200 && rect.width < 500 && grid.scrollHeight > grid.clientHeight) {
                return grid;
            }
        }
        
        // Strategy 2: Left sidebar scrollables
        const leftScrollables = Array.from(document.querySelectorAll('div')).filter(el => {
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return (style.overflowY === 'auto' || style.overflowY === 'scroll') &&
                   rect.width > 200 && rect.width < 500 && // Sidebar width constraints
                   rect.left < 500 && // Must be on left side
                   el.scrollHeight > el.clientHeight;
        });

        if (leftScrollables.length > 0) return leftScrollables[0];

        // Strategy 3: Any scrollable in main area (fallback)
        const scrollables = Array.from(document.querySelectorAll('div')).filter(el => {
             const style = window.getComputedStyle(el);
             return (style.overflowY === 'auto' || style.overflowY === 'scroll') && 
                    el.scrollHeight > el.clientHeight;
        });
        
        // Sort by height (usually the main list is tall)
        scrollables.sort((a, b) => b.clientHeight - a.clientHeight);
        return scrollables[0];
    }

    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `scroller-toast ${type}`;
        toast.innerText = message;
        document.body.appendChild(toast);
        
        // Trigger animation
        setTimeout(() => toast.classList.add('visible'), 10);
        
        // Remove after 3s
        setTimeout(() => {
            toast.classList.remove('visible');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    function startScrolling() {
        const container = findDMContainer();
        if (!container) {
            showToast('Could not find DM list!', 'error');
            return;
        }

        console.log('[InstaLogger][Scroller] Starting scroll...');
        showToast('Auto-Scroll Started', 'success');
        isScrolling = true;
        lastTickTime = Date.now();
        scrollAccumulator = 0;

        // UI Update
        startBtn.innerHTML = '<span>⏸</span> Stop';
        startBtn.classList.add('active');
        statusDot.classList.add('active');
        statusText.innerText = 'Status: Running';
        statusText.style.color = '#0095f6';

        // Start Loop
        requestNextTick();
    }

    function stopScrolling() {
        console.log('[InstaLogger][Scroller] Stopping scroll...');
        if (isScrolling) showToast('Auto-Scroll Stopped', 'info');
        isScrolling = false;
        if (scrollInterval) clearTimeout(scrollInterval);
        scrollInterval = null;

        // UI Update
        if (startBtn) {
            startBtn.innerHTML = '<span>▶</span> Start';
            startBtn.classList.remove('active');
        }
        if (statusDot) statusDot.classList.remove('active');
        if (statusText) {
            statusText.innerText = 'Status: Stopped';
            statusText.style.color = '#262626';
        }
    }

    function requestNextTick() {
        if (!isScrolling) return;
        // 50ms = 20 ticks per second (ideal)
        // In background, this might throttle to 1000ms (1 tick per second)
        scrollInterval = setTimeout(performScrollStep, 50); 
    }

    function performScrollStep() {
        if (!isScrolling) return;

        const container = findDMContainer();
        if (!container) {
            stopScrolling();
            return;
        }

        const now = Date.now();
        let dt = now - lastTickTime;
        lastTickTime = now;

        // SANITY CHECK: Cap delta time to prevent massive jumps if tab was frozen
        if (dt > 1500) dt = 1500; 

        // Calculate Pixels
        const pps = PRESETS[settings.speed].pixelsPerSecond;
        const pixels = (pps / 1000) * dt;
        
        scrollAccumulator += pixels;

        if (scrollAccumulator >= 1) {
            const step = Math.floor(scrollAccumulator);
            scrollAccumulator -= step;
            
            const currentScroll = container.scrollTop;
            const targetScroll = settings.direction === 'down' ? currentScroll + step : currentScroll - step;
            
            // 1. Perform the Scroll
            container.scrollTop = targetScroll;
            
            // 2. FORCE Event Dispatching to trigger Infinite Scroll
            // We use a variety of events to ensure frameworks (React/Instagram) pick it up.
            const eventOptions = { bubbles: true, cancelable: false, composed: true };
            
            // Standard scroll event
            container.dispatchEvent(new Event('scroll', eventOptions));
            
            // Wheel event (sometimes listened to for user activity)
            container.dispatchEvent(new WheelEvent('wheel', { ...eventOptions, deltaY: settings.direction === 'down' ? step : -step }));
            
            // Touch move simulation (mobile emulation sometimes triggers it)
            container.dispatchEvent(new TouchEvent('touchmove', eventOptions));

            // 3. Layout Thrashing (Force Reflow)
            // Reading scrollHeight forces the browser to recalculate layout, 
            // which often triggers IntersectionObservers in background tabs.
            const _ = container.scrollHeight; 
        }

        requestNextTick();
    }

    function scrollToTop() {
        const container = findDMContainer();
        if (container) {
            container.scrollTo({ top: 0, behavior: 'smooth' });
            // Dispatch scroll event after a small delay to ensure listeners fire
            setTimeout(() => container.dispatchEvent(new Event('scroll')), 500);
        }
    }

    function scrollToBottom() {
        const container = findDMContainer();
        if (container) {
            container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
            // Dispatch scroll event after a small delay to ensure listeners fire
            setTimeout(() => container.dispatchEvent(new Event('scroll')), 500);
        }
    }

    // =============================================================================
    // Lifecycle
    // =============================================================================

    function checkUrl() {
        const isDirect = window.location.href.includes('/direct/');
        if (isDirect) {
            if (!toggleBtn) createToggleButton();
            toggleBtn.style.display = 'flex';
        } else {
            if (toggleBtn) toggleBtn.style.display = 'none';
            if (panel) panel.style.display = 'none';
            stopScrolling();
        }
    }

    // Initialize
    setInterval(checkUrl, 1000); // Check URL periodically (SPA navigation)
    checkUrl();

})();
