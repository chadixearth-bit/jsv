document.addEventListener('DOMContentLoaded', function() {
    const detailButtons = document.querySelectorAll('.delivery-detail-btn');
    const modal = document.getElementById('deliveryDetailsModal');

    detailButtons.forEach(button => {
        button.addEventListener('click', function() {
            const deliveryId = this.getAttribute('data-delivery-id');
            if (deliveryId) {
                fetchWithCSRF(`/requisition/delivery/${deliveryId}/details/`, {
                    method: 'GET',
                })
                .then(response => response.json())
                .then(data => {
                    showDeliveryDetails(data);
                    modal.classList.remove('hidden');
                })
                .catch(error => console.error('Error fetching delivery details:', error));
            }
        });
    });

    function showDeliveryDetails(data) {
        // Populate modal with delivery details
        // Example: document.getElementById('modalDeliveryTitle').innerText = data.title;
    }

    document.getElementById('closeDetailsModal').addEventListener('click', function() {
        modal.classList.add('hidden');
    });
});
