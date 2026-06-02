// Run this in browser console (F12 → Console) on the Starlink usage page
// It will show you all clickable elements and chart structure

(function() {
    console.log('=== ALL CLICKABLE ELEMENTS ===');
    const clickables = Array.from(document.querySelectorAll('button, [role="tab"], [role="button"], a, div[onclick], span[onclick]'));
    clickables.forEach((el, i) => {
        const text = (el.innerText || el.textContent || '').trim();
        if (text && text.length < 50) {
            console.log(`[${i}] ${el.tagName} class="${el.className}" text="${text}"`);
        }
    });

    console.log('\n=== ELEMENTS WITH MONTH-LIKE TEXT ===');
    const allElements = Array.from(document.querySelectorAll('*'));
    allElements.forEach(el => {
        const text = (el.innerText || el.textContent || '').trim();
        if (/\b(Nov|Dec|Jan|Feb|Mar|Apr|May|Jun)\b/i.test(text) && text.length < 30) {
            console.log(`${el.tagName} class="${el.className}" text="${text}"`);
        }
    });

    console.log('\n=== SVG / CHART ELEMENTS ===');
    const svgs = document.querySelectorAll('svg');
    console.log(`Found ${svgs.length} SVG elements`);
    svgs.forEach((svg, i) => {
        const rects = svg.querySelectorAll('rect');
        console.log(`SVG[${i}]: ${rects.length} rect elements`);
        if (rects.length > 0 && rects.length < 50) {
            rects.forEach((r, j) => {
                console.log(`  rect[${j}]: height=${r.getAttribute('height')} y=${r.getAttribute('y')} class="${r.className}"`);
            });
        }
    });

    console.log('\n=== TOTAL USAGE TEXT ===');
    const allText = Array.from(document.querySelectorAll('h1, h2, h3, h4, span, div, p'));
    allText.forEach(el => {
        const text = (el.innerText || '').trim();
        if (/\d+\s*(GB|TB)/.test(text) && text.length < 100) {
            console.log(`${el.tagName} class="${el.className}": "${text}"`);
        }
    });
})();
