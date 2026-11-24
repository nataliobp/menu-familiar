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
            feedback.textContent = "No s’ha pogut confirmar el desament. Recarrega la plantilla per comprovar si s’ha desat o torna-ho a provar.";
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

function readPage(html) {
    return new DOMParser().parseFromString(html, "text/html");
}

const filterForm = document.querySelector("[data-live-filters]");
if (filterForm && window.fetch) {
    document.documentElement.classList.add("live-filters");
    const search = filterForm.elements.q;
    const category = filterForm.elements.category;
    const results = document.querySelector("[data-filter-results]");
    const filterError = document.querySelector("#filter-error");
    const count = filterForm.querySelector("[data-filter-count]");
    const icon = filterForm.querySelector("[data-filter-icon]");
    const pickerVersion = document.querySelector("[data-picker-version]")?.dataset.pickerVersion;
    let timer;
    let request;
    let composing = false;

    async function refreshResults() {
        const controller = new AbortController();
        request = controller;
        const url = new URL(location.href);
        url.search = new URLSearchParams(new FormData(filterForm)).toString();
        const timeout = setTimeout(() => controller.abort(), 10000);
        try {
            const response = await fetch(url, { signal: controller.signal });
            const page = readPage(await response.text());
            if (controller !== request) return;
            const nextResults = page.querySelector("[data-filter-results]");
            if (!nextResults) throw new Error("Missing results");
            const error = page.querySelector("#filter-error").textContent;
            filterError.textContent = error;
            filterError.hidden = !error;
            results.replaceChildren(...nextResults.childNodes);
            // Filtering must not silently rebase a pending planning edit.
            if (pickerVersion !== undefined) {
                results.querySelectorAll('[name="version"]').forEach((field) => {
                    field.value = pickerVersion;
                });
            }
            count.textContent = page.querySelector("[data-filter-count]").textContent.trim();
            icon.replaceChildren(...page.querySelector("[data-filter-icon]").childNodes);
            results.inert = false;
            history.replaceState(history.state, "", url);
        } catch {
            if (controller !== request) return;
            filterError.textContent = "No s’han pogut actualitzar els resultats.";
            const retry = document.createElement("button");
            retry.type = "button";
            retry.textContent = "Torna-ho a provar";
            retry.addEventListener("click", () => schedule(0));
            filterError.append(" ", retry);
            filterError.hidden = false;
        } finally {
            clearTimeout(timeout);
            if (controller === request) results.removeAttribute("aria-busy");
        }
    }

    function schedule(delay) {
        clearTimeout(timer);
        request?.abort();
        request = undefined;
        if (composing) return;
        results.inert = true;
        results.setAttribute("aria-busy", "true");
        timer = setTimeout(refreshResults, delay);
    }

    search.addEventListener("compositionstart", () => {
        composing = true;
        schedule(0);
    });
    search.addEventListener("compositionend", () => {
        composing = false;
        schedule(250);
    });
    search.addEventListener("input", () => schedule(250));
    category.addEventListener("change", () => schedule(0));
    filterForm.addEventListener("submit", (event) => {
        event.preventDefault();
        schedule(0);
    });
}

const confirmation = document.querySelector("#confirmation");
const confirmContent = confirmation?.querySelector("[data-confirm-content]");
let confirmTrigger;
let confirmRequest;
let commandBusy = false;
let lockedControls = [];

function showCommandError(container, message, reviewURL) {
    const error = container.querySelector("[data-command-error]");
    const review = container.querySelector("[data-command-review]");
    error.textContent = message;
    error.hidden = false;
    if (reviewURL) review.href = reviewURL;
    review.hidden = !reviewURL;
    (reviewURL ? review : error).focus();
}

if (confirmation?.showModal) {
    function openConfirmation(trigger, fragment) {
        confirmRequest?.abort();
        confirmRequest = undefined;
        confirmTrigger = trigger;
        confirmation.querySelector("#confirmation-title").textContent =
            fragment.querySelector("[data-confirm-heading]").textContent;
        fragment.querySelector("[data-confirm-heading]").remove();
        const description = fragment.querySelector("[data-confirm-description]");
        description.id = "confirmation-description";
        const extraDescription = description.nextElementSibling;
        if (extraDescription?.matches("p")) {
            extraDescription.id = "confirmation-consequence";
            confirmation.setAttribute("aria-describedby", "confirmation-description confirmation-consequence");
        } else {
            confirmation.setAttribute("aria-describedby", "confirmation-description");
        }
        confirmContent.replaceChildren(fragment);
        confirmation.querySelector("[data-command-error]").hidden = true;
        confirmation.querySelector("[data-command-review]").hidden = true;
        confirmation.showModal();
        confirmContent.querySelector("[data-confirm-cancel]").focus();
    }

    function confirmationFailure(trigger, stale) {
        const fragment = document.getElementById("confirmation-failure").content.cloneNode(true);
        fragment.querySelector("[data-confirm-heading]").textContent = stale ?
            "El contingut ha canviat" : "No s’ha pogut obrir la confirmació";
        fragment.querySelector("[data-confirm-reload]").href = location.href;
        openConfirmation(trigger, fragment);
    }

    const discardForm = document.querySelector("[data-discard-form]");
    const formValues = (form) => new URLSearchParams(new FormData(form)).toString();
    const savedValues = discardForm ? formValues(discardForm) : "";

    document.querySelectorAll("[data-confirm], [data-confirm-template]").forEach((trigger) => {
        trigger.setAttribute("aria-haspopup", "dialog");
    });
    document.addEventListener("click", async (event) => {
        if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        const trigger = event.target.closest("[data-confirm], [data-confirm-template]");
        if (!trigger) return;
        event.preventDefault();
        if (trigger.dataset.confirmTemplate) {
            const fragment = document.getElementById(trigger.dataset.confirmTemplate).content.cloneNode(true);
            if (discardForm && !discardForm.hasAttribute("data-unsaved") && formValues(discardForm) === savedValues) {
                location.assign(fragment.querySelector("[data-discard-destination]").href);
            } else {
                openConfirmation(trigger, fragment);
            }
            return;
        }
        confirmRequest?.abort();
        const controller = new AbortController();
        confirmRequest = controller;
        const timeout = setTimeout(() => controller.abort(), 10000);
        try {
            const response = await fetch(trigger.href, { signal: controller.signal });
            const page = readPage(await response.text());
            if (controller !== confirmRequest || !trigger.isConnected) return;
            const fragment = page.querySelector("[data-confirmation]");
            if (response.ok && fragment) {
                openConfirmation(trigger, fragment);
            } else {
                confirmationFailure(trigger, response.status === 409);
            }
        } catch {
            if (controller === confirmRequest && trigger.isConnected) confirmationFailure(trigger, false);
        } finally {
            clearTimeout(timeout);
        }
    });
    confirmation.addEventListener("click", (event) => {
        if (event.target.closest("[data-confirm-cancel]")) {
            event.preventDefault();
            if (!commandBusy) confirmation.close();
        }
    });
    confirmation.addEventListener("pointerdown", (event) => {
        confirmation.dataset.backdrop = String(event.target === confirmation);
    });
    confirmation.addEventListener("click", (event) => {
        if (confirmation.dataset.backdrop === "true" && event.target === confirmation && !commandBusy) {
            const bounds = confirmation.getBoundingClientRect();
            if (event.clientX < bounds.left || event.clientX > bounds.right ||
                event.clientY < bounds.top || event.clientY > bounds.bottom) confirmation.close();
        }
    });
    confirmation.addEventListener("cancel", (event) => {
        if (commandBusy) event.preventDefault();
    });
    confirmation.addEventListener("close", () => {
        confirmContent.replaceChildren();
        confirmTrigger?.focus();
    });
    sheet?.addEventListener("close", () => {
        if (!confirmation.open) cancelConfirmationRead();
    });
}

function cancelConfirmationRead() {
    confirmRequest?.abort();
    confirmRequest = undefined;
}

const pickerPending = document.querySelector("[data-picker-pending]");
function unlockCommand() {
    commandBusy = false;
    lockedControls.forEach((control) => { control.disabled = false; });
    lockedControls = [];
    if (pickerPending) pickerPending.hidden = true;
}

document.addEventListener("submit", async (event) => {
    const form = event.target;
    const modal = confirmation?.contains(form);
    if (!modal && !form.matches("[data-picker-choice], [data-direct-command]")) return;
    const area = modal ? confirmation : document.querySelector("main");
    if (!area.querySelector("[data-command-error]")) return;
    event.preventDefault();
    if (commandBusy || !area.querySelector("[data-command-review]").hidden) return;
    const data = new FormData(form, event.submitter);
    commandBusy = true;
    lockedControls = Array.from(area.querySelectorAll(
        modal ? "button:not(:disabled)" :
            "[data-picker-choice] button:not(:disabled), [data-direct-command] button:not(:disabled), [data-live-filters] input:not(:disabled), [data-live-filters] select:not(:disabled)"
    ));
    lockedControls.forEach((control) => { control.disabled = true; });
    area.querySelector("[data-command-error]").hidden = true;
    if (pickerPending) pickerPending.hidden = false;

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
        const response = await fetch(form.action, {
            method: "POST", headers: { Accept: "application/json" },
            body: data, signal: controller.signal,
        });
        if (response.ok) {
            const result = await response.json();
            if (typeof result.location !== "string" || !result.location.startsWith("/") ||
                result.location.startsWith("//")) throw new Error("Missing destination");
            location.assign(result.location);
            return;
        }
        unlockCommand();
        if (response.status === 409) {
            const page = readPage(await response.text());
            const recovery = modal ? null : page.querySelector("[data-recovery]")?.getAttribute("href");
            area.querySelectorAll("[data-picker-choice] button, [data-direct-command] button, [data-confirm-content] form button").forEach((button) => {
                button.disabled = true;
            });
            showCommandError(area, "El contingut ha canviat. Revisa’l abans de tornar-ho a provar.", recovery || location.href);
        } else {
            showCommandError(area, "No s’ha pogut desar el canvi. Comprova les dades i torna-ho a provar.");
        }
    } catch {
        unlockCommand();
        showCommandError(area, "No s’ha pogut confirmar el desament. Recarrega la pàgina per comprovar si s’ha desat o torna-ho a provar.");
    } finally {
        clearTimeout(timeout);
    }
});

window.addEventListener("pageshow", () => {
    unlockCommand();
});
window.addEventListener("pagehide", () => {
    cancelConfirmationRead();
    confirmation?.close();
    sheet?.close();
});

const copyRecipePrompt = document.querySelector("[data-copy-recipe-prompt]");
if (copyRecipePrompt) {
    const prompt = document.getElementById("recipe-import-prompt");
    const status = document.getElementById("recipe-import-copy-status");
    copyRecipePrompt.hidden = false;
    copyRecipePrompt.addEventListener("click", async () => {
        let copied = false;
        if (navigator.clipboard?.writeText) {
            try {
                await navigator.clipboard.writeText(prompt.value);
                copied = true;
            } catch {
                // Fall back to selecting the prompt on browsers without clipboard access.
            }
        }
        if (!copied) {
            prompt.focus();
            prompt.select();
            copied = document.execCommand?.("copy");
        }
        status.textContent = copied ? "Instrucció copiada." : "Copia el text seleccionat.";
    });
}
