(() => {
    const sidebar = document.querySelector("#sidebar");
    const openButton = document.querySelector("[data-sidebar-open]");
    const closeButton = document.querySelector("[data-sidebar-close]");

    if (sidebar && openButton && closeButton) {
        const setOpen = (open) => {
            document.body.classList.toggle("sidebar-open", open);
            openButton.setAttribute("aria-expanded", String(open));
        };

        openButton.addEventListener("click", () => setOpen(true));
        closeButton.addEventListener("click", () => setOpen(false));
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") setOpen(false);
        });
    }

    const root = document.documentElement;
    const themeButton = document.querySelector("[data-theme-toggle]");
    const themeLabel = document.querySelector("[data-theme-label]");
    const status = document.querySelector("[data-a11y-status]");
    const fontButtons = {
        decrease: document.querySelector("[data-font-decrease]"),
        reset: document.querySelector("[data-font-reset]"),
        increase: document.querySelector("[data-font-increase]"),
    };
    const storageKeys = { theme: "jay-marques-theme", scale: "jay-marques-font-scale" };
    const minScale = 0.8;
    const maxScale = 1.4;
    let fontScale = 1;
    let fontSizeSnapshot = [];

    const readPreference = (key) => {
        try {
            return window.localStorage.getItem(key);
        } catch (_error) {
            return null;
        }
    };

    const savePreference = (key, value) => {
        try {
            window.localStorage.setItem(key, value);
        } catch (_error) {
            // A preferência continua válida nesta página mesmo se o armazenamento estiver bloqueado.
        }
    };

    const announce = (message) => {
        if (status) status.textContent = message;
    };

    const applyTheme = (theme, shouldSave = false) => {
        const isDark = theme === "dark";
        root.dataset.theme = isDark ? "dark" : "light";
        const themeColor = document.querySelector('meta[name="theme-color"]');
        if (themeColor) themeColor.content = isDark ? "#09060e" : "#f8f6fa";
        if (themeButton) {
            themeButton.setAttribute("aria-pressed", String(isDark));
            const action = isDark ? "Ativar tema claro" : "Ativar tema escuro";
            themeButton.setAttribute("aria-label", `Tema ${isDark ? "escuro" : "claro"} ativo. ${action}`);
            themeButton.title = action;
            if (themeLabel) themeLabel.textContent = action;
        }
        if (shouldSave) savePreference(storageKeys.theme, isDark ? "dark" : "light");
    };

    const captureFontSizes = () => {
        for (const [element] of fontSizeSnapshot) element.style.removeProperty("font-size");
        fontSizeSnapshot = Array.from(document.body.querySelectorAll("*:not(svg):not(script):not(style):not(path):not(circle):not(rect):not(line):not(polyline):not(polygon)"))
            .map((element) => [element, window.getComputedStyle(element).fontSize]);
    };

    const applyFontScale = (scale, shouldSave = false) => {
        fontScale = Math.min(maxScale, Math.max(minScale, scale));
        if (!fontSizeSnapshot.length) captureFontSizes();
        for (const [element, baseSize] of fontSizeSnapshot) {
            element.style.setProperty("font-size", `calc(${baseSize} * ${fontScale})`);
        }
        root.dataset.fontScale = fontScale.toFixed(1);
        if (shouldSave) savePreference(storageKeys.scale, fontScale.toFixed(1));
        announce(`Tamanho da fonte: ${Math.round(fontScale * 100)} por cento.`);
    };

    applyTheme(readPreference(storageKeys.theme) === "dark" ? "dark" : "light");
    const storedScale = Number.parseFloat(readPreference(storageKeys.scale));
    applyFontScale(Number.isFinite(storedScale) ? storedScale : 1);

    themeButton?.addEventListener("click", () => {
        const nextTheme = root.dataset.theme === "dark" ? "light" : "dark";
        applyTheme(nextTheme, true);
        announce(`Tema ${nextTheme === "dark" ? "escuro" : "claro"} ativado.`);
    });
    fontButtons.decrease?.addEventListener("click", () => applyFontScale(fontScale - 0.1, true));
    fontButtons.reset?.addEventListener("click", () => applyFontScale(1, true));
    fontButtons.increase?.addEventListener("click", () => applyFontScale(fontScale + 0.1, true));

    const passwordToggle = document.querySelector("[data-password-toggle]");
    const passwordField = passwordToggle ? document.getElementById(passwordToggle.getAttribute("aria-controls")) : null;
    passwordToggle?.addEventListener("click", () => {
        if (!passwordField) return;
        const shouldShow = passwordField.type === "password";
        passwordField.type = shouldShow ? "text" : "password";
        passwordToggle.setAttribute("aria-pressed", String(shouldShow));
        passwordToggle.setAttribute("aria-label", shouldShow ? "Ocultar senha" : "Mostrar senha");
        passwordToggle.textContent = shouldShow ? "Ocultar" : "Mostrar";
    });

    window.addEventListener("resize", () => {
        captureFontSizes();
        applyFontScale(fontScale);
    });
})();
