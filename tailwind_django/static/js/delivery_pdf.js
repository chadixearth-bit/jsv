// Wait for the DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // CSRF token setup
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    const csrftoken = getCookie('csrftoken');

    // Fetch with CSRF utility function
    window.fetchWithCSRF = function(url, options = {}) {
        options.headers = {
            ...options.headers,
            'X-CSRFToken': csrftoken,
        };
        return fetch(url, options);
    };

    // Add event listeners for PDF generation buttons if they exist
    const pdfButtons = document.querySelectorAll('.generate-pdf-btn');
    if (pdfButtons) {
        pdfButtons.forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                const deliveryId = this.getAttribute('data-delivery-id');
                if (deliveryId) {
                    window.location.href = `/requisition/delivery/${deliveryId}/pdf/`;
                }
            });
        });
    }
});
