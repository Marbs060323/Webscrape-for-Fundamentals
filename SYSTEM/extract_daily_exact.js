/**
 * Starlink Daily Data Extractor - Exact Values
 * ==============================================
 * This script hovers over every chart bar to read the exact tooltip values.
 * Run this in browser console (F12 -> Console) on the Starlink usage page.
 */

(async function() {
    const sleep = ms => new Promise(r => setTimeout(r, ms));
    const allData = [];

    // Find clickable month tabs
    const allEls = Array.from(document.querySelectorAll('*'));
    const seenTexts = new Set();
    const tabCandidates = [];
    for (const el of allEls) {
        const text = (el.innerText || el.textContent || '').trim();
        if (/^(Nov\s*-\s*Dec|Nov|Dec|Jan|Feb|Mar|Apr|May|Jun)$/i.test(text)) {
            if (!seenTexts.has(text)) {
                seenTexts.add(text);
                tabCandidates.push(el);
            }
        }
    }
    const tabs = tabCandidates.filter(el => typeof el.click === 'function' && el.offsetParent !== null);

    console.log(`Found ${tabs.length} month tabs:`, tabs.map(t => (t.innerText||t.textContent).trim()));

    for (const tab of tabs) {
        tab.click();
        await sleep(3000); // Wait for chart to fully render

        const monthText = (tab.innerText || tab.textContent || '').trim();
        console.log(`\n--- ${monthText} ---`);

        // STRATEGY 1: Systematic hover over chart area to trigger tooltips
        const bars = [];

        // Get chart container - try multiple selectors
        const chartSelectors = [
            'canvas',
            'svg',
            '[data-testid*="chart"]',
            '[data-testid*="usage"]',
            '.recharts-wrapper',
            '[class*="chart"]',
            '[class*="usage"]'
        ];

        let chartEl = null;
        for (const sel of chartSelectors) {
            chartEl = document.querySelector(sel);
            if (chartEl) {
                console.log(`  Found chart element: ${sel}`);
                break;
            }
        }

        if (!chartEl) {
            console.log('  No chart element found');
            allData.push({month: monthText, bars: []});
            continue;
        }

        const rect = chartEl.getBoundingClientRect();
        console.log(`  Chart size: ${rect.width}x${rect.height} at (${rect.left}, ${rect.top})`);

        // Divide chart into ~31 vertical strips and hover at each position
        const numStrips = 31;
        const step = rect.width / numStrips;

        for (let i = 0; i < numStrips; i++) {
            const x = rect.left + (i * step) + (step / 2);
            const y = rect.top + (rect.height / 2);

            // Move mouse to this position
            chartEl.dispatchEvent(new MouseEvent('mousemove', {
                bubbles: true,
                clientX: x,
                clientY: y,
                relatedTarget: chartEl
            }));

            await sleep(200);

            // Look for tooltip - search all visible elements
            const tooltip = findTooltip();
            if (tooltip) {
                console.log(`  Strip ${i+1}: ${tooltip.text}`);
                if (tooltip.date && tooltip.value !== null) {
                    bars.push({
                        date: tooltip.date,
                        value: tooltip.value,
                        raw: tooltip.text
                    });
                }
            }
        }

        // Deduplicate by date
        const seenDates = new Set();
        const uniqueBars = [];
        for (const b of bars) {
            if (!seenDates.has(b.date)) {
                seenDates.add(b.date);
                uniqueBars.push(b);
            }
        }

        console.log(`  Total unique daily bars: ${uniqueBars.length}`);
        uniqueBars.forEach(b => console.log(`    ${b.date}: ${b.value.toFixed(2)} GB`));

        allData.push({month: monthText, bars: uniqueBars});
    }

    console.log('\n========== COMPLETE ==========');
    console.log(JSON.stringify(allData, null, 2));

    // Build CSV
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
    a.download = 'starlink_daily_exact.csv';
    a.click();
    URL.revokeObjectURL(url);

    console.log('\nCSV downloaded: starlink_daily_exact.csv');

    // Helper: find tooltip by scanning DOM
    function findTooltip() {
        // Method 1: Look for elements with both date and GB/TB
        const allDivs = document.querySelectorAll('div, span, p, h1, h2, h3, h4');
        for (const el of allDivs) {
            const text = (el.innerText || el.textContent || '').trim();
            // Match patterns like "Jan 15" and "12.5 GB" in the same element
            const hasDate = /\b(Nov|Dec|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct)\s+\d{1,2}\b/i.test(text);
            const hasValue = /(\d+(?:\.\d+)?)\s*(GB|TB|MB)/i.test(text);
            if (hasDate && hasValue && text.length < 200) {
                const dateMatch = text.match(/\b(Nov|Dec|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct)\s+(\d{1,2})\b/i);
                const valMatch = text.match(/(\d+(?:\.\d+)?)\s*(GB|TB|MB)/i);
                if (dateMatch && valMatch) {
                    let val = parseFloat(valMatch[1]);
                    const unit = valMatch[2];
                    if (unit === 'TB') val *= 1024;
                    if (unit === 'MB') val /= 1024;
                    return {date: `${dateMatch[1]} ${dateMatch[2]}`, value: val, text};
                }
            }
        }

        // Method 2: Look for tooltip-specific elements
        const tooltipEls = document.querySelectorAll(
            '[data-testid*="tooltip"], .recharts-tooltip-wrapper, [class*="tooltip"], [role="tooltip"]'
        );
        for (const el of tooltipEls) {
            const text = (el.innerText || el.textContent || '').trim();
            if (text) {
                const dateMatch = text.match(/\b(Nov|Dec|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct)\s+(\d{1,2})\b/i);
                const valMatch = text.match(/(\d+(?:\.\d+)?)\s*(GB|TB|MB)/i);
                if (dateMatch && valMatch) {
                    let val = parseFloat(valMatch[1]);
                    const unit = valMatch[2];
                    if (unit === 'TB') val *= 1024;
                    if (unit === 'MB') val /= 1024;
                    return {date: `${dateMatch[1]} ${dateMatch[2]}`, value: val, text};
                }
            }
        }

        return null;
    }
})();
