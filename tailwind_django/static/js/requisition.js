// Store selected items and their quantities
let selectedItems = new Map();
let lastSelectedItem = null;

function toggleItemSelection(element, itemId, itemName, event) {
    event.preventDefault(); // Prevent default click behavior
    
    const isCtrlPressed = event.ctrlKey || event.metaKey;
    const isShiftPressed = event.shiftKey;
    
    // Handle Shift+Click
    if (isShiftPressed && lastSelectedItem) {
        const allItems = Array.from(document.querySelectorAll('.item-card'));
        const currentIndex = allItems.indexOf(element);
        const lastIndex = allItems.indexOf(lastSelectedItem);
        
        const start = Math.min(currentIndex, lastIndex);
        const end = Math.max(currentIndex, lastIndex);
        
        for (let i = start; i <= end; i++) {
            const item = allItems[i];
            const itemData = item.getAttribute('onclick').match(/toggleItemSelection\(this,\s*'([^']+)',\s*'([^']+)'/);
            if (itemData) {
                selectItem(item, itemData[1], itemData[2]);
            }
        }
        return;
    }
    
    // If Ctrl is not pressed, deselect all other items
    if (!isCtrlPressed) {
        document.querySelectorAll('.item-card.selected').forEach(item => {
            if (item !== element) {
                const itemData = item.getAttribute('onclick').match(/toggleItemSelection\(this,\s*'([^']+)',\s*'([^']+)'/);
                if (itemData) {
                    deselectItem(item, itemData[1]);
                }
            }
        });
    }
    
    // Toggle current item
    if (element.classList.contains('selected')) {
        deselectItem(element, itemId);
    } else {
        selectItem(element, itemId, itemName);
    }
    
    lastSelectedItem = element;
}

function selectItem(element, itemId, itemName) {
    if (!selectedItems.has(itemId)) {
        element.classList.add('selected');
        selectedItems.set(itemId, {
            name: itemName,
            quantity: 1
        });
        
        // Add animation classes
        element.querySelector('.selection-overlay').style.opacity = '1';
        element.querySelector('.checkmark-icon').style.transform = 'scale(1)';
        
        createQuantityField(itemId, itemName);
        updateQuantitiesInput();
        updateSelectedItemsDisplay();
    }
}

function deselectItem(element, itemId) {
    if (selectedItems.has(itemId)) {
        element.classList.remove('selected');
        selectedItems.delete(itemId);
        
        // Remove animation classes with transition
        element.querySelector('.selection-overlay').style.opacity = '0';
        element.querySelector('.checkmark-icon').style.transform = 'scale(0)';
        
        removeItem(itemId);
        updateQuantitiesInput();
        updateSelectedItemsDisplay();
    }
}

function createQuantityField(itemId, itemName) {
    const quantityFields = document.getElementById('quantityFields');
    
    // Remove the "No items selected" message if it exists
    const noItemsMessage = quantityFields.querySelector('.no-items-message');
    if (noItemsMessage) {
        noItemsMessage.remove();
    }
    
    // Create the quantity field HTML
    const fieldHtml = `
        <div id="quantity-field-${itemId}" class="flex items-center justify-between p-4 bg-white rounded-lg shadow-sm border border-gray-100 hover:border-indigo-200 transition-colors duration-200">
            <div class="flex items-center space-x-3">
                <i class="fas fa-box text-indigo-500"></i>
                <span class="font-medium text-gray-800">${itemName}</span>
            </div>
            <div class="flex items-center space-x-4">
                <div class="flex items-center space-x-2">
                    <button type="button" onclick="adjustQuantity('${itemId}', -1)" 
                            class="w-8 h-8 rounded-full flex items-center justify-center text-gray-500 hover:text-indigo-600 hover:bg-indigo-50 transition-colors">
                        <i class="fas fa-minus"></i>
                    </button>
                    <input type="number" min="1" value="1" 
                           class="w-16 text-center border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
                           onchange="updateItemQuantity('${itemId}', this.value)">
                    <button type="button" onclick="adjustQuantity('${itemId}', 1)"
                            class="w-8 h-8 rounded-full flex items-center justify-center text-gray-500 hover:text-indigo-600 hover:bg-indigo-50 transition-colors">
                        <i class="fas fa-plus"></i>
                    </button>
                </div>
                <button type="button" onclick="removeItem('${itemId}')"
                        class="w-8 h-8 rounded-full flex items-center justify-center text-red-500 hover:text-red-600 hover:bg-red-50 transition-colors">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        </div>
    `;
    
    // Add the new field
    quantityFields.insertAdjacentHTML('beforeend', fieldHtml);
}

function adjustQuantity(itemId, delta) {
    const input = document.getElementById(`quantity-${itemId}`);
    if (input) {
        const currentValue = parseInt(input.value) || 1;
        const newValue = Math.max(1, currentValue + delta);
        input.value = newValue;
        updateItemQuantity(itemId, newValue);
    }
}

function removeItem(itemId) {
    const element = document.querySelector(`.item-card[onclick*="'${itemId}'"]`);
    const quantityField = document.getElementById(`quantity-field-${itemId}`);
    
    if (element) {
        deselectItem(element, itemId);
    }
    
    if (quantityField) {
        quantityField.remove();
    }
    
    // If no items are selected, show the message
    if (selectedItems.size === 0) {
        const quantityFields = document.getElementById('quantityFields');
        quantityFields.innerHTML = '<div class="text-gray-500 text-sm italic p-4 no-items-message">No items selected</div>';
    }
}

function updateItemQuantity(itemId, value) {
    if (!selectedItems.has(itemId)) return;
    
    // Get the max stock from the item card
    const itemCard = document.querySelector(`.item-card[onclick*="${itemId}"]`);
    const stockText = itemCard.querySelector('.stock-text').textContent;
    const maxStock = parseInt(stockText.match(/\d+/)[0]);
    
    // Validate and update quantity
    let quantity = parseInt(value);
    if (isNaN(quantity) || quantity < 1) {
        quantity = 1;
    } else if (quantity > maxStock) {
        quantity = maxStock;
        // Show error message
        const quantityField = document.getElementById(`quantity-field-${itemId}`);
        const errorMsg = quantityField.querySelector('.error-message') || document.createElement('div');
        errorMsg.className = 'error-message text-red-500 text-sm mt-1';
        errorMsg.textContent = `Maximum available stock is ${maxStock}`;
        quantityField.appendChild(errorMsg);
    }
    
    selectedItems.get(itemId).quantity = quantity;
    document.getElementById(`quantity-${itemId}`).value = quantity;
    updateQuantitiesInput();
}

function updateQuantitiesInput() {
    const quantitiesInput = document.querySelector('input[name="quantities"]');
    const quantities = Array.from(selectedItems.entries()).map(([id, { quantity }]) => `${id}:${quantity}`);
    quantitiesInput.value = quantities.join(',');
}

function updateSelectedItemsDisplay() {
    const selectedItemsContainer = document.getElementById('selectedItemsContainer');
    const selectedItemsList = document.getElementById('selectedItemsList');
    
    if (selectedItems.size > 0) {
        selectedItemsContainer.classList.remove('hidden');
        selectedItemsList.innerHTML = '';
        
        selectedItems.forEach(({ name, quantity }, itemId) => {
            const itemElement = document.createElement('div');
            itemElement.className = 'flex items-center justify-between p-4 bg-white rounded-lg shadow-sm border border-gray-100 hover:border-indigo-200 transition-colors duration-200';
            itemElement.innerHTML = `
                <div class="flex items-center space-x-3">
                    <i class="fas fa-box text-indigo-500"></i>
                    <span class="font-medium text-gray-800">${name}</span>
                </div>
                <div class="flex items-center space-x-4">
                    <div class="flex items-center space-x-2">
                        <button type="button" onclick="adjustQuantity('${itemId}', -1)" 
                                class="w-8 h-8 rounded-full flex items-center justify-center text-gray-500 hover:text-indigo-600 hover:bg-indigo-50 transition-colors">
                            <i class="fas fa-minus"></i>
                        </button>
                        <input type="number" min="1" value="${quantity}" 
                               class="w-16 text-center border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
                               onchange="updateItemQuantity('${itemId}', this.value)">
                        <button type="button" onclick="adjustQuantity('${itemId}', 1)"
                                class="w-8 h-8 rounded-full flex items-center justify-center text-gray-500 hover:text-indigo-600 hover:bg-indigo-50 transition-colors">
                            <i class="fas fa-plus"></i>
                        </button>
                    </div>
                    <button type="button" onclick="removeItem('${itemId}')"
                            class="w-8 h-8 rounded-full flex items-center justify-center text-red-500 hover:text-red-600 hover:bg-red-50 transition-colors">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            `;
            selectedItemsList.appendChild(itemElement);
        });
    } else {
        selectedItemsContainer.classList.add('hidden');
        selectedItemsList.innerHTML = '<div class="text-gray-500 text-sm italic p-4">No items selected</div>';
    }
}

// Form submission handler
document.getElementById('requisitionForm').addEventListener('submit', function(event) {
    event.preventDefault();
    
    // Validate request type
    const requestType = document.querySelector('select[name="request_type"]');
    if (!requestType.value) {
        showError(requestType, 'Please select a request type');
        return;
    }
    
    // Validate items selection
    if (selectedItems.size === 0) {
        const itemsContainer = document.querySelector('.items-container');
        showError(itemsContainer, 'Please select at least one item');
        return;
    }
    
    // Validate quantities
    let hasQuantityError = false;
    selectedItems.forEach((item, itemId) => {
        const itemCard = document.querySelector(`.item-card[onclick*="${itemId}"]`);
        const stockText = itemCard.querySelector('.stock-text').textContent;
        const maxStock = parseInt(stockText.match(/\d+/)[0]);
        
        if (item.quantity > maxStock) {
            hasQuantityError = true;
            const quantityField = document.getElementById(`quantity-field-${itemId}`);
            showError(quantityField, `Maximum available stock for ${item.name} is ${maxStock}`);
        }
    });
    
    if (hasQuantityError) return;
    
    // If all validations pass, submit the form
    this.submit();
});

function showError(element, message) {
    // Remove any existing error messages
    const existingError = element.parentElement.querySelector('.error-message');
    if (existingError) existingError.remove();
    
    // Create and show new error message
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message text-red-500 text-sm mt-1';
    errorDiv.textContent = message;
    element.parentElement.appendChild(errorDiv);
    
    // Highlight the element
    element.classList.add('border-red-500');
    
    // Remove error after 5 seconds
    setTimeout(() => {
        errorDiv.remove();
        element.classList.remove('border-red-500');
    }, 5000);
}

// Initialize any existing selections
document.addEventListener('DOMContentLoaded', function() {
    const itemsInput = document.querySelector('input[name="items"]');
    const quantitiesInput = document.querySelector('input[name="quantities"]');
    
    if (itemsInput.value && quantitiesInput.value) {
        const selectedIds = itemsInput.value.split(',');
        const quantities = {};
        
        quantitiesInput.value.split(',').forEach(pair => {
            const [id, qty] = pair.split(':');
            quantities[id] = parseInt(qty);
        });
        
        selectedIds.forEach(itemId => {
            const element = document.querySelector(`.item-card[onclick*="${itemId}"]`);
            if (element) {
                const itemName = element.querySelector('h3').textContent.trim();
                element.classList.add('selected');
                element.querySelector('.selection-overlay').style.opacity = '1';
                element.querySelector('.checkmark-icon').style.transform = 'scale(1)';
                
                selectedItems.set(itemId, {
                    name: itemName,
                    quantity: parseInt(quantities[itemId]) || 1
                });
            }
        });
        
        updateSelectedItemsDisplay();
    }
});
