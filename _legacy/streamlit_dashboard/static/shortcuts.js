// Injected inside a components.html iframe. The iframe carries `allow-same-origin`,
// so it can reach the parent Streamlit document to listen for keystrokes globally
// and navigate the top-level window. A plain <script> in st.markdown is stripped by
// Streamlit's HTML sanitizer, which is why this runs from an iframe instead.
(function () {
    var win = window.parent;
    var doc = win.document;

    // Avoid stacking duplicate listeners across Streamlit reruns.
    if (win.__ccShortcutsBound) return;
    win.__ccShortcutsBound = true;

    var shortcuts = {
        '1': '/',            // Home
        '2': '/Tasks',
        '3': '/Projects',
        'i': '/Inbox',
        '/': '/Search',
    };

    doc.addEventListener('keydown', function (e) {
        // Ctrl only — ignore when combined with Alt/Meta (avoids browser chords).
        if (!e.ctrlKey || e.altKey || e.metaKey) return;

        // Don't hijack keys while the user is typing in a field.
        var t = e.target || {};
        var tag = (t.tagName || '').toLowerCase();
        if (tag === 'input' || tag === 'textarea' || t.isContentEditable) return;

        var path = shortcuts[(e.key || '').toLowerCase()];
        if (path) {
            e.preventDefault();
            win.location.pathname = path;
        }
    });
})();
