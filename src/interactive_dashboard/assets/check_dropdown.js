// Close open checkbox dropdowns (see _check_dropdown in app.py) when the user
// presses anywhere outside them, or hits Escape; opening one therefore closes
// the others. Listening on pointerdown in the capture phase means no component
// (tables, graphs, tabs) can swallow the event before it gets here.
(function () {
    function closeDropdowns(except) {
        document
            .querySelectorAll("details.check-dropdown[open]")
            .forEach(function (dropdown) {
                if (!except || !dropdown.contains(except)) {
                    dropdown.removeAttribute("open");
                }
            });
    }

    document.addEventListener(
        "pointerdown",
        function (event) {
            closeDropdowns(event.target);
        },
        true
    );
    document.addEventListener(
        "keydown",
        function (event) {
            if (event.key === "Escape") {
                closeDropdowns(null);
            }
        },
        true
    );
})();
