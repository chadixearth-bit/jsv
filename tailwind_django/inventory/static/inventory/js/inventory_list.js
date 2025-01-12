// Function to filter items based on search term
function filterItems(searchTerm) {
    const tableRows = document.querySelectorAll('table tbody tr');
    
    tableRows.forEach(row => {
        const itemNameCell = row.querySelector('td:nth-child(1)');
        const brandCell = row.querySelector('td:nth-child(2)');
        const modelCell = row.querySelector('td:nth-child(3)');
        
        if (!itemNameCell || !brandCell || !modelCell) return;
        
        const itemName = itemNameCell.textContent.toLowerCase().trim();
        const brand = brandCell.textContent.toLowerCase().trim();
        const model = modelCell.textContent.toLowerCase().trim();
        
        if (searchTerm === '') {
            row.style.display = '';
        } else {
            const matches = itemName.startsWith(searchTerm) || 
                          brand.startsWith(searchTerm) || 
                          model.startsWith(searchTerm);
            row.style.display = matches ? '' : 'none';
        }
    });
}

// Function to filter by brand
function filterByBrand(brandId) {
    const tableRows = document.querySelectorAll('table tbody tr');
    
    tableRows.forEach(row => {
        if (!brandId) {
            row.style.display = '';
            return;
        }
        
        const brandCell = row.querySelector('td:nth-child(2)');
        if (!brandCell) return;
        
        const currentBrandId = brandCell.getAttribute('data-brand-id');
        row.style.display = (currentBrandId === brandId) ? '' : 'none';
    });
}

// Function to filter by category
function filterByCategory(categoryId) {
    const tableRows = document.querySelectorAll('table tbody tr');
    
    tableRows.forEach(row => {
        if (!categoryId) {
            row.style.display = '';
            return;
        }
        
        const categoryCell = row.querySelector('td:nth-child(3)');
        if (!categoryCell) return;
        
        const currentCategoryId = categoryCell.getAttribute('data-category-id');
        row.style.display = (currentCategoryId === categoryId) ? '' : 'none';
    });
}

// Initialize event listeners when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Search input handler
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const searchTerm = e.target.value.toLowerCase().trim();
            filterItems(searchTerm);
        });
    }
    
    // Brand filter handler
    const brandSelect = document.getElementById('brand');
    if (brandSelect) {
        brandSelect.addEventListener('change', (e) => {
            filterByBrand(e.target.value);
        });
    }
    
    // Category filter handler
    const categorySelect = document.getElementById('category');
    if (categorySelect) {
        categorySelect.addEventListener('change', (e) => {
            filterByCategory(e.target.value);
        });
    }
    
    // Log initial setup
    console.log('Filters initialized');
});
