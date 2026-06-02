/**
 * Starlink Data Extractor v3
 * ==========================
 * Run this in browser console (F12 → Console) on the Starlink usage page.
 * Fixes click errors, extracts daily data from hidden elements / React state.
 */

(async function() {
    const sleep = ms => new Promise(r => setTimeout(r, ms));
    const allData = [];

    // Find clickable tabs only (actual HTMLElement with click method)
    const allEls = Array.from(document.querySelectorAll('*'));
    const tabCandidates = [];
    const seenTexts = new Set();
    for (const el of allEls) {
        const text = (el.innerText || el.textContent || '').trim();
        if (/^(Nov\s*-\s*Dec|Nov|Dec|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct)$/i.test(text)) {
            if (!seenTexts.has(text)) {
                seenTexts.add(text);
                tabCandidates.push(el);
            }
        }
    }
    // Filter to only elements that are actually clickable
    const tabs = tabCandidates.filter(el => typeof el.click === 'function' && el.offsetParent !== null);

    console.log(`Found ${tabs.length} clickable month tabs:`, tabs.map(t => (t.innerText||t.textContent).trim()));
    if (tabs.length === 0) {
        console.error('No month tabs found. Make sure you are on the usage page.');
        return;
    }

    for (const tab of tabs) {
        tab.click();
        await sleep(2500);

        const monthText = (tab.innerText || tab.textContent || '').trim();
        console.log(`\n--- ${monthText} ---`);

        // Find total usage
        let totalGB = '';
        const pageText = document.body.innerText;
        const totalMatch = pageText.match(/Total\s+Data\s+Usage\s*\n?\s*(\d+(?:\.\d+)?)\s*(GB|TB)/i);
        if (totalMatch) {
            totalGB = totalMatch[1];
            console.log(`  Total: ${totalGB} ${totalMatch[2]}`);
        }

        // Try multiple methods to extract daily data
        const bars = [];

        // METHOD 1: Look for hidden data in script tags or JSON
        const scripts = document.querySelectorAll('script[type="application/json"], script:not([type])');
        for (const script of scripts) {
            const text = script.innerText || script.textContent || '';
            // Look for data that might contain daily usage
            const jsonMatches = text.match(/\{[^}]*"date"[^}]*\}/g) || [];
            for (const match of jsonMatches) {
                try {
                    const obj = JSON.parse(match);
                    if (obj.date && (obj.usage || obj.data || obj.total || obj.value)) {
                        bars.push({date: obj.date, value: parseFloat(obj.usage || obj.data || obj.total || obj.value), raw: JSON.stringify(obj)});
                    }
                } catch(e) {}
            }
        }

        // METHOD 2: Look for data attributes on chart elements
        const chartEls = document.querySelectorAll('[data-date], [data-value], [data-usage]');
        for (const el of chartEls) {
            const date = el.getAttribute('data-date') || el.getAttribute('data-day');
            const val = el.getAttribute('data-value') || el.getAttribute('data-usage');
            if (date && val) {
                bars.push({date, value: parseFloat(val), raw: 'data-attribute'});
            }
        }

        // METHOD 3: Try to read from React internal props (if React DevTools isn't needed)
        const reactRoots = document.querySelectorAll('[data-reactroot], #root, #app');
        for (const root of reactRoots) {
            const keys = Object.keys(root);
            for (const key of keys) {
                if (key.startsWith('__react')) {
                    try {
                        const fiber = root[key];
                        // Walk the fiber tree looking for usage data
                        let node = fiber;
                        while (node) {
                            const props = node.memoizedProps || node.pendingProps;
                            if (props && Array.isArray(props.data)) {
                                for (const item of props.data) {
                                    if (item.date && (item.usage || item.value || item.total)) {
                                        bars.push({date: item.date, value: parseFloat(item.usage || item.value || item.total), raw: 'react-props'});
                                    }
                                }
                            }
                            node = node.child || node.sibling;
                        }
                    } catch(e) {}
                }
            }
        }

        // METHOD 4: Canvas chart - try to extract from page variables
        // Starlink might store chart data in a global variable
        for (const key of Object.keys(window)) {
            try {
                const val = window[key];
                if (typeof val === 'object' && val !== null) {
                    // Check if it's an array of daily data
                    if (Array.isArray(val) && val.length > 5 && val.length < 50) {
                        for (const item of val) {
                            if (typeof item === 'object' && item.date && (item.usage || item.data || item.total || item.value)) {
                                bars.push({date: item.date, value: parseFloat(item.usage || item.data || item.total || item.value), raw: 'window-var'});
                            }
                        }
                    }
                }
            } catch(e) {}
        }

        // METHOD 5: Look for table or list with daily data
        const rows = document.querySelectorAll('tr, [role="row"]');
        for (const row of rows) {
            const cells = row.querySelectorAll('td, [role="cell"]');
            if (cells.length >= 2) {
                const texts = Array.from(cells).map(c => (c.innerText || '').trim());
                const dateMatch = texts[0].match(/\b(Nov|Dec|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct)\s+(\d{1,2})\b/i) || texts[0].match(/\d{4}-\d{2}-\d{2}/);
                const valMatch = texts.find(t => /\d+\.?\d*\s*(GB|TB|MB)/.test(t));
                if (dateMatch && valMatch) {
                    const v = valMatch.match(/(\d+(?:\.\d+)?)\s*(GB|TB|MB)/);
                    const gb = v[2] === 'TB' ? parseFloat(v[1])*1024 : v[2] === 'MB' ? parseFloat(v[1])/1024 : parseFloat(v[1]);
                    bars.push({date: texts[0], value: gb, raw: 'table-row'});
                }
            }
        }

        // Deduplicate bars by date
        const seenDates = new Set();
        const uniqueBars = [];
        for (const b of bars) {
            if (!seenDates.has(b.date)) {
                seenDates.add(b.date);
                uniqueBars.push(b);
            }
        }

        console.log(`  Found ${uniqueBars.length} daily bars`);
        uniqueBars.forEach(b => console.log(`    ${b.date}: ${b.value.toFixed(2)} GB`));

        allData.push({month: monthText, total: totalGB, bars: uniqueBars});
    }

    console.log('\n========== MONTHLY SUMMARY ==========');
    allData.forEach(m => {
        console.log(`${m.month}: ${m.total} GB total, ${m.bars.length} days`);
    });

    console.log('\n========== FULL JSON ==========');
    console.log(JSON.stringify(allData, null, 2));

    // Build and download CSV
    let csv = 'month,date,value_gb\n';
    allData.forEach(m => {
        m.bars.forEach(b => {
            csv += `"${m.month}","${b.date}",${b.value.toFixed(2)}\n`;
        });
    });

    const blob = new Blob([csv], {type: 'text/csv'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'starlink_usage.csv';
    a.click();
    URL.revokeObjectURL(url);

    console.log('\nCSV downloaded: starlink_usage.csv');
})();
