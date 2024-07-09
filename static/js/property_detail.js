document.addEventListener('DOMContentLoaded', function () {
    // Initialize date pickers
    flatpickr(".datepicker", {
        dateFormat: "Y-m-d",
        altInput: true,
        altFormat: "F j, Y",
        allowInput: true
    });

    // Payment method handling for expense and payable forms
    const paymentMethodSelects = document.querySelectorAll('.payment_method_type');
    paymentMethodSelects.forEach(select => {
        const form = select.closest('form');
        const creditCardField = form.querySelector('.credit_card_field');
        const checkNumberField = form.querySelector('.check_number_field');

        select.addEventListener('change', function () {
            if (this.value === 'Credit Card') {
                creditCardField.style.display = 'block';
                checkNumberField.style.display = 'none';
            } else if (this.value === 'Check') {
                creditCardField.style.display = 'none';
                checkNumberField.style.display = 'block';
            } else {
                creditCardField.style.display = 'none';
                checkNumberField.style.display = 'none';
            }
        });
    });

    // Vendor suggestions
    const vendorInputs = document.querySelectorAll('input[name="vendor"]');
    vendorInputs.forEach(input => {
        const suggestionsList = input.nextElementSibling;

        input.addEventListener('input', function () {
            const query = this.value.toLowerCase();
            if (query.length < 2) {
                suggestionsList.innerHTML = '';
                suggestionsList.style.display = 'none';
                return;
            }

            fetch(`/vendor-suggestions?query=${encodeURIComponent(query)}`)
                .then(response => response.json())
                .then(data => {
                    suggestionsList.innerHTML = '';
                    data.forEach(vendor => {
                        const item = document.createElement('a');
                        item.classList.add('dropdown-item');
                        item.href = '#';
                        item.textContent = vendor;
                        item.addEventListener('click', function (e) {
                            e.preventDefault();
                            input.value = this.textContent;
                            suggestionsList.style.display = 'none';
                        });
                        suggestionsList.appendChild(item);
                    });
                    suggestionsList.style.display = data.length ? 'block' : 'none';
                });
        });

        document.addEventListener('click', function (e) {
            if (e.target !== input && e.target !== suggestionsList) {
                suggestionsList.style.display = 'none';
            }
        });
    });

    // Payable payment modal handling
    const paymentModal = new bootstrap.Modal(document.getElementById('paymentModal'));
    const paymentForm = document.getElementById('paymentForm');
    const modalPaymentMethodSelect = document.getElementById('modal_payment_method_type');
    const modalCreditCardField = document.getElementById('modal_credit_card_field');
    const modalCheckNumberField = document.getElementById('modal_check_number_field');

    modalPaymentMethodSelect.addEventListener('change', function () {
        if (this.value === 'Credit Card') {
            modalCreditCardField.style.display = 'block';
            modalCheckNumberField.style.display = 'none';
        } else if (this.value === 'Check') {
            modalCreditCardField.style.display = 'none';
            modalCheckNumberField.style.display = 'block';
        } else {
            modalCreditCardField.style.display = 'none';
            modalCheckNumberField.style.display = 'none';
        }
    });

    document.getElementById('submitPaymentForm').addEventListener('click', function (e) {
        e.preventDefault();
        if (paymentForm.checkValidity()) {
            paymentForm.submit();
        } else {
            paymentForm.reportValidity();
        }
    });

    // Handle "Mark as Paid" button clicks
    document.querySelectorAll('.mark-as-paid-btn').forEach(button => {
        button.addEventListener('click', function () {
            const payableId = this.getAttribute('data-payable-id');
            paymentForm.action = `/payable/${payableId}/mark-as-paid`;
            paymentModal.show();
        });
    });

    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });
});