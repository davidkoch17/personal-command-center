document.addEventListener('keydown', function(e) {
    if (!e.ctrlKey) return;
    const shortcuts = {
        '1': '/',                      // Home
        '2': '/Tasks',
        '3': '/Projects',
        'i': '/Inbox',
        '/': '/Search',
    };
    const path = shortcuts[e.key.toLowerCase()];
    if (path) {
        e.preventDefault();
        window.location.pathname = path;
    }
});
