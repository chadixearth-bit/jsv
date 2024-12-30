// Debounce function to limit API calls
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

class DynamicSearch {
    constructor(searchInputId, resultsContainerId, options = {}) {
        this.searchInput = document.getElementById(searchInputId);
        this.resultsContainer = document.getElementById(resultsContainerId);
        this.options = {
            minChars: options.minChars || 1,
            debounceMs: options.debounceMs || 300,
            searchEndpoint: options.searchEndpoint || '/requisition/api/v1/search-items/',
            onSelect: options.onSelect || null,
            resultTemplate: options.resultTemplate || this.defaultTemplate,
            noResultsTemplate: options.noResultsTemplate || '<div class="text-gray-500 p-4">No results found</div>',
            loadingTemplate: options.loadingTemplate || '<div class="text-gray-500 p-4">Searching...</div>'
        };

        this.setupEventListeners();
    }

    setupEventListeners() {
        // Debounced search function
        this.debouncedSearch = debounce(
            () => this.performSearch(),
            this.options.debounceMs
        );

        // Add input event listener
        this.searchInput.addEventListener('input', () => {
            const query = this.searchInput.value.trim();
            if (query.length >= this.options.minChars) {
                this.showLoading();
                this.debouncedSearch();
            } else {
                this.clearResults();
            }
        });

        // Add click event listener to handle result selection
        this.resultsContainer.addEventListener('click', (e) => {
            const resultItem = e.target.closest('[data-result-id]');
            if (resultItem && this.options.onSelect) {
                const itemData = {
                    id: resultItem.dataset.resultId,
                    name: resultItem.dataset.resultName,
                    stock: parseInt(resultItem.dataset.resultStock, 10),
                    brand: resultItem.dataset.resultBrand,
                    warehouse: resultItem.dataset.resultWarehouse
                };
                this.options.onSelect(itemData);
                this.clearResults();
                this.searchInput.value = '';
            }
        });

        // Close results when clicking outside
        document.addEventListener('click', (e) => {
            if (!this.searchInput.contains(e.target) && !this.resultsContainer.contains(e.target)) {
                this.clearResults();
            }
        });
    }

    async performSearch() {
        const query = this.searchInput.value.trim();
        if (!query) {
            this.clearResults();
            return;
        }

        try {
            const response = await fetch(`${this.options.searchEndpoint}?q=${encodeURIComponent(query)}`, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (!response.ok) {
                throw new Error('Search request failed');
            }

            const results = await response.json();
            this.displayResults(results);
        } catch (error) {
            console.error('Search error:', error);
            this.displayError('An error occurred while searching');
        }
    }

    displayResults(results) {
        if (!Array.isArray(results) || results.length === 0) {
            this.resultsContainer.innerHTML = this.options.noResultsTemplate;
            return;
        }

        const resultsHtml = results.map(result => this.options.resultTemplate(result)).join('');
        this.resultsContainer.innerHTML = resultsHtml;
        this.resultsContainer.classList.remove('hidden');
    }

    showLoading() {
        this.resultsContainer.innerHTML = this.options.loadingTemplate;
        this.resultsContainer.classList.remove('hidden');
    }

    clearResults() {
        this.resultsContainer.innerHTML = '';
        this.resultsContainer.classList.add('hidden');
    }

    displayError(message) {
        this.resultsContainer.innerHTML = `<div class="text-red-500 p-4">${message}</div>`;
        this.resultsContainer.classList.remove('hidden');
    }

    defaultTemplate(item) {
        return `
            <div class="p-4 hover:bg-gray-50 cursor-pointer flex justify-between items-center"
                 data-result-id="${item.id}"
                 data-result-name="${item.item_name}"
                 data-result-stock="${item.stock}"
                 data-result-brand="${item.brand}"
                 data-result-warehouse="${item.warehouse}">
                <div>
                    <div class="font-medium">${item.item_name}</div>
                    <div class="text-sm text-gray-500">
                        Brand: ${item.brand} | Warehouse: ${item.warehouse}
                    </div>
                </div>
                <div class="text-sm text-gray-600">
                    Stock: ${item.stock}
                </div>
            </div>
        `;
    }
}

// Export the class
window.DynamicSearch = DynamicSearch;
