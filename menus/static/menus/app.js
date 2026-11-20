const sheet = document.querySelector("#sheet");
if (sheet?.showModal) {
    document.documentElement.classList.add("has-dialog");
    document.querySelectorAll("a[data-sheet], a[data-category-trigger]").forEach((link) => {
        link.setAttribute("aria-haspopup", "dialog");
    });
    const content = sheet.querySelector("[data-sheet-content]");
    const heading = sheet.querySelector("#sheet-title");
    const closeButton = sheet.querySelector("[data-sheet-close]");
    let trigger;
    let busy = false;

    function openSheet(link, template) {
        trigger = link;
        heading.textContent = link.dataset.heading;
        content.replaceChildren(template.content.cloneNode(true));
        sheet.showModal();
        closeButton.focus();
    }

    document.addEventListener("click", (event) => {
        const link = event.target.closest("a[data-sheet], a[data-category-trigger]");
        if (!link || event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        const template = document.getElementById(link.dataset.sheet || "category-choices");
        if (!template) return;
        event.preventDefault();
        openSheet(link, template);

        const form = content.querySelector("[data-category-form]");
        if (form) {
            form.action = link.href;
            form.elements.version.value = link.closest("[data-template-version]").dataset.templateVersion;
            form.querySelectorAll(".category-choice").forEach((choice) => {
                choice.setAttribute("aria-pressed", String(choice.value === link.dataset.category));
            });
        }
    });

    closeButton.addEventListener("click", () => sheet.close());
    sheet.addEventListener("cancel", (event) => {
        if (busy) event.preventDefault();
    });
    function onBackdrop(event) {
        const bounds = sheet.getBoundingClientRect();
        return event.target === sheet && (
            event.clientX < bounds.left || event.clientX > bounds.right ||
            event.clientY < bounds.top || event.clientY > bounds.bottom
        );
    }

    let backdropPressed = false;
    sheet.addEventListener("pointerdown", (event) => {
        backdropPressed = onBackdrop(event);
    });
    sheet.addEventListener("click", (event) => {
        if (backdropPressed && onBackdrop(event) && !busy) sheet.close();
    });
    sheet.addEventListener("close", () => {
        content.replaceChildren();
        trigger?.focus();
    });

    content.addEventListener("submit", async (event) => {
        const form = event.target;
        if (!form.matches("[data-category-form]")) return;
        event.preventDefault();
        const choice = event.submitter;
        if (busy || !choice || choice.disabled) return;

        const choices = form.querySelectorAll(".category-choice");
        const feedback = form.querySelector("[data-category-error]");
        const pending = form.querySelector("[data-category-pending]");
        const reload = form.querySelector("[data-template-reload]");
        const data = new FormData(form);
        data.set("category", choice.value);
        busy = closeButton.disabled = true;
        const grid = form.querySelector(".category-grid");
        grid.setAttribute("aria-busy", "true");
        choices.forEach((button) => { button.disabled = true; });
        pending.hidden = false;
        feedback.hidden = true;
        let stale = false;
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 10000);
        try {
            const response = await fetch(form.action, {
                method: "POST",
                headers: { Accept: "application/json" },
                body: data,
                signal: controller.signal,
            });
            if (response.ok) {
                const result = await response.json();
                const display = trigger.querySelector(".category-display");
                display.replaceChildren(...Array.from(choice.children, (child) => child.cloneNode(true)));
                display.lastElementChild.textContent = result.label;
                trigger.dataset.category = result.category;
                trigger.closest("[data-template-version]").dataset.templateVersion = result.version;
                document.querySelector("[data-template-status]").textContent = "Plantilla actualitzada";
                sheet.close();
                return;
            }
            stale = response.status === 409;
            const isJson = response.headers.get("Content-Type")?.includes("application/json");
            const result = isJson ? await response.json() : {};
            feedback.textContent = result.error || "No s’ha pogut desar la categoria. Torna-ho a provar.";
        } catch {
            feedback.textContent = "No s’ha pogut confirmar el desament. Actualitza la plantilla per comprovar-lo o torna-ho a provar.";
            reload.hidden = false;
        } finally {
            busy = closeButton.disabled = false;
            clearTimeout(timeout);
            grid.removeAttribute("aria-busy");
            pending.hidden = true;
            choices.forEach((button) => { button.disabled = stale; });
        }
        feedback.hidden = false;
        if (stale) {
            reload.hidden = false;
            reload.focus();
        } else {
            choice.focus();
        }
    });
}

const pickerPending = document.querySelector("[data-picker-pending]");
if (pickerPending) {
    const buttons = document.querySelectorAll("[data-picker-choice] button");
    document.addEventListener("submit", (event) => {
        if (!event.target.matches("[data-picker-choice]")) return;
        if (!pickerPending.hidden) {
            event.preventDefault();
            return;
        }
        pickerPending.hidden = false;
        for (const button of buttons) button.disabled = true;
    });
    window.addEventListener("pageshow", () => {
        pickerPending.hidden = true;
        for (const button of buttons) button.disabled = false;
    });
}
