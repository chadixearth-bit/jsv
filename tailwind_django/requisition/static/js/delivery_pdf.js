function openPdfModal(deliveryId) {
    const modal = document.getElementById('pdfModal');
    const pdfViewer = document.getElementById('pdfViewer');
    pdfViewer.src = `/requisition/delivery/pdf/${deliveryId}/`;
    modal.classList.remove('hidden');
    // Prevent body scrolling when modal is open
    document.body.style.overflow = 'hidden';
}

function closePdfModal() {
    const modal = document.getElementById('pdfModal');
    const pdfViewer = document.getElementById('pdfViewer');
    pdfViewer.src = '';
    modal.classList.add('hidden');
    // Restore body scrolling
    document.body.style.overflow = 'auto';
}

// Close modal when clicking outside
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('pdfModal').addEventListener('click', function(e) {
        if (e.target === this) {
            closePdfModal();
        }
    });

    // Close modal on escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closePdfModal();
        }
    });
});

// Function to download delivery PDF
function downloadDeliveryPDF(deliveryId) {
    console.log('Downloading PDF for delivery:', deliveryId);
    window.open(`/requisition/delivery/pdf/${deliveryId}/`, '_blank');
}

// Function to handle PDF download button click
document.addEventListener('DOMContentLoaded', function() {
    const pdfButtons = document.querySelectorAll('[data-pdf-delivery]');
    pdfButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const deliveryId = this.getAttribute('data-pdf-delivery');
            downloadDeliveryPDF(deliveryId);
        });
    });
});
