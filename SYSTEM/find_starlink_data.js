/**
 * Starlink Data Finder
 * ====================
 * Searches the entire page for usage data arrays.
 * Run this in browser console (F12 -> Console) on the Starlink usage page.
 */

(function() {
    console.log('=== SEARCHING FOR DATA ===\n');

    // 1. Check window object for arrays with date+usage
    console.log('1. Checking window variables...');
    for (const key of Object.keys(window)) {
        try {
            const val = window[key];
            if (Array.isArray(val) && val.length > 5) {
                const sample = val[0];
                if (sample && typeof sample === 'object') {
                    const keys = Object.keys(sample).join(',');
                    if (/date|usage|data|total|bytes/i.test(keys)) {
                        console.log(`FOUND in window.${key}:`, keys);
                        console.log('Sample:', JSON.stringify(sample).slice(0, 200));
                    }
                }
            }
        } catch(e) {}
    }

    // 2. Check localStorage
    console.log('\n2. Checking localStorage...');
    for (const key of Object.keys(localStorage)) {
        const val = localStorage.getItem(key);
        if (val && val.length < 5000 && /date|usage|data|total|bytes/i.test(val)) {
            console.log(`localStorage["${key}"]:`, val.slice(0, 200));
        }
    }

    // 3. Check sessionStorage
    console.log('\n3. Checking sessionStorage...');
    for (const key of Object.keys(sessionStorage)) {
        const val = sessionStorage.getItem(key);
        if (val && val.length < 5000 && /date|usage|data|total|bytes/i.test(val)) {
            console.log(`sessionStorage["${key}"]:`, val.slice(0, 200));
        }
    }

    // 4. Look for Redux/React dev data
    console.log('\n4. Checking for React/Redux state...');
    const roots = document.querySelectorAll('#root, #app, [data-reactroot]');
    roots.forEach((root, i) => {
        const keys = Object.keys(root);
        keys.forEach(k => {
            if (k.startsWith('__react')) {
                try {
                    const fiber = root[k];
                    console.log(`React root[${i}] has fiber:`, k);
                    // Try to find data in memoizedState
                    let node = fiber;
                    let depth = 0;
                    while (node && depth < 20) {
                        if (node.memoizedState && typeof node.memoizedState === 'object') {
                            const state = node.memoizedState;
                            const stateKeys = Object.keys(state);
                            if (stateKeys.some(sk => /data|usage|chart|series/i.test(sk))) {
                                console.log('  Found state keys:', stateKeys.filter(sk => /data|usage|chart|series/i.test(sk)));
                            }
                        }
                        node = node.child || node.sibling;
                        depth++;
                    }
                } catch(e) {}
            }
        });
    });

    // 5. Look at all script tags for JSON data
    console.log('\n5. Checking script tags for JSON...');
    const scripts = document.querySelectorAll('script');
    scripts.forEach((script, i) => {
        const text = script.innerText || script.textContent || '';
        if (text.length > 100 && text.length < 10000) {
            const matches = text.match(/"date"[:\s]*"[^"]+"/g);
            if (matches && matches.length > 5) {
                console.log(`Script[${i}] has ${matches.length} date entries`);
                console.log('  Sample:', text.slice(0, 300));
            }
        }
    });

    // 6. Look for canvas elements (chart might be canvas-based)
    console.log('\n6. Canvas elements:');
    const canvases = document.querySelectorAll('canvas');
    console.log(`Found ${canvases.length} canvas elements`);
    canvases.forEach((c, i) => {
        console.log(`  Canvas[${i}]: ${c.width}x${c.height}`);
    });

    console.log('\n=== DONE ===');
    console.log('If you found data above, copy the variable name or JSON and paste it here.');
})();
