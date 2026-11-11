(() => {
    const sidebar = document.querySelector("#sidebar");
    const openButton = document.querySelector("[data-sidebar-open]");
    const closeButton = document.querySelector("[data-sidebar-close]");

    if (!sidebar || !openButton || !closeButton) return;

    const setOpen = (open) => {
        document.body.classList.toggle("sidebar-open", open);
        openButton.setAttribute("aria-expanded", String(open));
    };

    openButton.addEventListener("click", () => setOpen(true));
    closeButton.addEventListener("click", () => setOpen(false));
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") setOpen(false);
    });
})();
