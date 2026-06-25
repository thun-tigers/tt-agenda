(function () {
    function normalize(value) {
        return (value || "").toLowerCase().replace(/\s+/g, " ").trim();
    }

    function parseTimeToMinutes(value) {
        const match = /^([0-2]?\d):([0-5]\d)$/.exec((value || "").trim());
        if (!match) {
            return Number.MAX_SAFE_INTEGER;
        }
        return Number(match[1]) * 60 + Number(match[2]);
    }

    function iconClassForSort(state) {
        if (state === "asc") {
            return "bi-sort-numeric-down";
        }
        if (state === "desc") {
            return "bi-sort-numeric-up";
        }
        return "bi-arrow-down-up";
    }

    function sortTitleForState(state) {
        if (state === "asc") {
            return "Sortierung: Startzeit aufsteigend";
        }
        if (state === "desc") {
            return "Sortierung: Startzeit absteigend";
        }
        return "Sortierung aus";
    }

    function initSmartList(list) {
        const items = Array.from(list.querySelectorAll("[data-smart-list-item]"));
        if (!items.length) {
            return;
        }

        const originalOrder = new Map(items.map((item, index) => [item, index]));
        const state = {
            filter: "",
            sort: "none"
        };

        const controlsHostId = list.dataset.controlsHost || "";
        const controlsHost = controlsHostId ? document.getElementById(controlsHostId) : null;
        if (!controlsHost) {
            return;
        }

        controlsHost.classList.add("relative", "flex", "items-center", "gap-2", "shrink-0");

        const filterButton = document.createElement("button");
        filterButton.type = "button";
        filterButton.className = "inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-300 text-slate-600 hover:bg-slate-100 hover:text-indigo-600 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700 dark:hover:text-indigo-400";
        filterButton.title = "Filter einblenden";
        filterButton.setAttribute("aria-label", "Filter einblenden");
        filterButton.innerHTML = '<i class="bi bi-funnel"></i>';

        const sortButton = document.createElement("button");
        sortButton.type = "button";
        sortButton.className = "inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-300 text-slate-600 hover:bg-slate-100 hover:text-indigo-600 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700 dark:hover:text-indigo-400";
        sortButton.title = sortTitleForState(state.sort);
        sortButton.setAttribute("aria-label", "Sortierung umschalten");
        sortButton.innerHTML = '<i class="bi ' + iconClassForSort(state.sort) + '"></i>';

        const filterPanel = document.createElement("div");
        filterPanel.className = "hidden absolute right-0 top-full z-30 mt-2 min-w-[16rem] rounded-lg border border-slate-200 bg-white p-3 shadow-xl dark:border-slate-700 dark:bg-slate-800";

        const input = document.createElement("input");
        input.type = "search";
        input.placeholder = "Aktivitäten filtern...";
        input.className = "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 dark:border-slate-600 dark:bg-slate-700 dark:text-white";

        const clearButton = document.createElement("button");
        clearButton.type = "button";
        clearButton.className = "mt-2 inline-flex items-center gap-1 text-xs font-medium text-slate-600 hover:text-indigo-600 dark:text-slate-300 dark:hover:text-indigo-400";
        clearButton.innerHTML = '<i class="bi bi-x-circle"></i>Zuruecksetzen';

        filterPanel.appendChild(input);
        filterPanel.appendChild(clearButton);
        controlsHost.appendChild(filterButton);
        controlsHost.appendChild(sortButton);
        controlsHost.appendChild(filterPanel);

        function getSortedItems() {
            const copy = items.slice();
            if (state.sort === "none") {
                copy.sort((a, b) => originalOrder.get(a) - originalOrder.get(b));
                return copy;
            }

            copy.sort((a, b) => {
                const aTime = parseTimeToMinutes(a.dataset.sortTime || "");
                const bTime = parseTimeToMinutes(b.dataset.sortTime || "");
                if (aTime !== bTime) {
                    return state.sort === "asc" ? aTime - bTime : bTime - aTime;
                }

                const aTitle = normalize(a.querySelector("h4") ? a.querySelector("h4").textContent : a.textContent);
                const bTitle = normalize(b.querySelector("h4") ? b.querySelector("h4").textContent : b.textContent);
                if (aTitle < bTitle) {
                    return state.sort === "asc" ? -1 : 1;
                }
                if (aTitle > bTitle) {
                    return state.sort === "asc" ? 1 : -1;
                }

                return originalOrder.get(a) - originalOrder.get(b);
            });

            return copy;
        }

        function applyState() {
            const sorted = getSortedItems();
            sorted.forEach((item) => list.appendChild(item));

            const query = normalize(state.filter);
            sorted.forEach((item) => {
                const haystack = normalize(item.dataset.search || item.textContent || "");
                item.style.display = !query || haystack.includes(query) ? "" : "none";
            });

            sortButton.innerHTML = '<i class="bi ' + iconClassForSort(state.sort) + '"></i>';
            sortButton.title = sortTitleForState(state.sort);
            sortButton.setAttribute("aria-label", sortTitleForState(state.sort));

            const hasFilter = !!query;
            filterButton.classList.toggle("text-indigo-600", hasFilter);
            filterButton.classList.toggle("dark:text-indigo-400", hasFilter);
            filterButton.classList.toggle("border-indigo-300", hasFilter);
            filterButton.classList.toggle("dark:border-indigo-600", hasFilter);
        }

        filterButton.addEventListener("click", () => {
            const open = !filterPanel.classList.contains("hidden");
            filterPanel.classList.toggle("hidden", open);
            filterButton.title = open ? "Filter einblenden" : "Filter ausblenden";
            filterButton.setAttribute("aria-label", open ? "Filter einblenden" : "Filter ausblenden");
            if (!open) {
                input.focus();
            }
        });

        sortButton.addEventListener("click", () => {
            if (state.sort === "none") {
                state.sort = "asc";
            } else if (state.sort === "asc") {
                state.sort = "desc";
            } else {
                state.sort = "none";
            }
            applyState();
        });

        input.addEventListener("input", () => {
            state.filter = input.value || "";
            applyState();
        });

        clearButton.addEventListener("click", () => {
            state.filter = "";
            input.value = "";
            applyState();
            input.focus();
        });

        document.addEventListener("click", (event) => {
            if (!controlsHost.contains(event.target)) {
                filterPanel.classList.add("hidden");
                filterButton.title = "Filter einblenden";
                filterButton.setAttribute("aria-label", "Filter einblenden");
            }
        });

        applyState();
    }

    function init() {
        document.querySelectorAll(".js-smart-list").forEach(initSmartList);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
