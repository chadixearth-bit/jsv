// Function to fetch and display delivery details
async function fetchDeliveryDetails(deliveryId) {
    try {
        const response = await fetch(`/requisition/delivery/${deliveryId}/details/`, {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json'
            }
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Failed to fetch delivery details');
        }

        const data = await response.json();
        showDeliveryModal(data);
    } catch (error) {
        console.error('Error:', error);
        alert(error.message || 'Failed to load delivery details. Please try again.');
    }
}

// Function to show the delivery modal
function showDeliveryModal(deliveryData) {
    const modal = document.getElementById('deliveryModal');
    if (!modal) {
        console.error('Modal element not found');
        return;
    }

    // Update modal content with delivery data
    document.getElementById('deliveryId').textContent = deliveryData.id;
    document.getElementById('sourceWarehouse').textContent = deliveryData.source_warehouse;
    document.getElementById('destWarehouse').textContent = deliveryData.destination_warehouse;
    document.getElementById('deliveryStatus').textContent = deliveryData.status;
    document.getElementById('createdDate').textContent = deliveryData.created_at;
    document.getElementById('estimatedDate').textContent = deliveryData.estimated_delivery_date || 'Not specified';

    // Clear and populate items table
    const tableBody = document.getElementById('itemsTableBody');
    if (!tableBody) {
        console.error('Table body element not found');
        return;
    }

    tableBody.innerHTML = '';
    deliveryData.items.forEach(item => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${item.item_name}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${item.brand}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${item.category}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${item.quantity}</td>
        `;
        tableBody.appendChild(row);
    });

    // Show modal
    modal.classList.remove('hidden');
}

// Function to close the delivery modal
function closeDeliveryModal() {
    const modal = document.getElementById('deliveryModal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

// Function to download delivery PDF
function downloadDeliveryPDF(deliveryId) {
    window.open(`/requisition/delivery/${deliveryId}/pdf/`, '_blank');
}

// Set up event listeners
document.addEventListener('DOMContentLoaded', function() {
    // Modal close on outside click
    const modal = document.getElementById('deliveryModal');
    if (modal) {
        modal.addEventListener('click', function(event) {
            if (event.target === modal) {
                closeDeliveryModal();
            }
        });

        // Close modal on escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                closeDeliveryModal();
            }
        });
    }

    // Set up click handlers for view details buttons
    const viewButtons = document.querySelectorAll('[data-delivery-id]');
    viewButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const deliveryId = this.getAttribute('data-delivery-id');
            fetchDeliveryDetails(deliveryId);
        });
    });

    // Set up click handlers for PDF download buttons
    const pdfButtons = document.querySelectorAll('[data-pdf-delivery]');
    pdfButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const deliveryId = this.getAttribute('data-pdf-delivery');
            downloadDeliveryPDF(deliveryId);
        });
    });
});
